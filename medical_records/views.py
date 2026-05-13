import json
import re
from datetime import datetime, time
from zoneinfo import ZoneInfo

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db import transaction

from .models import MedicalRecord
from core.models import Notification
from appointments.models import Appointment
from core.decorators import role_required
from dental_records.models import DentalRecord
from health_forms_services.models import Prescription
from health_forms_services.forms import PrescriptionPatientForm
from django.contrib.auth import get_user_model


User = get_user_model()


def _build_prescription_initial(student, doctor=None):
    initial = {
        'date': timezone.now().date(),
    }

    if not student:
        return initial

    initial['patient_name'] = student.get_full_name()

    profile = getattr(student, 'student_profile', None)
    if profile and getattr(profile, 'date_of_birth', None):
        today = timezone.localdate()
        initial['age'] = today.year - profile.date_of_birth.year - ((today.month, today.day) < (profile.date_of_birth.month, profile.date_of_birth.day))

    if profile and getattr(profile, 'gender', None):
        initial['gender'] = profile.gender

    # Auto-select the physician if a doctor is provided
    if doctor:
        initial['physician'] = doctor.id

    return initial


def _collect_medication_entries(post_data):
    med_item_pattern = re.compile(r'^med_item_(\d+)_name$')
    med_indices = set()

    for key in post_data:
        match = med_item_pattern.match(key)
        if match:
            med_indices.add(int(match.group(1)))

    entries = []
    for idx in sorted(med_indices):
        entries.append({
            'name': post_data.get(f'med_item_{idx}_name', '').strip(),
            'dosage': post_data.get(f'med_item_{idx}_dosage', '').strip(),
            'frequency': post_data.get(f'med_item_{idx}_frequency', '').strip(),
            'duration': post_data.get(f'med_item_{idx}_duration', '').strip(),
            'quantity': post_data.get(f'med_item_{idx}_quantity', '').strip(),
            'instructions': post_data.get(f'med_item_{idx}_instructions', '').strip(),
        })

    return entries or [{'name': '', 'dosage': '', 'frequency': '', 'duration': '', 'quantity': '', 'instructions': ''}]


def _build_create_medical_record_context(request, *, appointment=None, student=None, prescription_form=None, is_direct_student_flow=False):
    if prescription_form is None:
        doctor = appointment.doctor if appointment else None
        prescription_form = PrescriptionPatientForm(initial=_build_prescription_initial(student or (appointment.student if appointment else None), doctor=doctor))

    context = {
        'appointment': appointment,
        'student': student,
        'is_direct_student_flow': is_direct_student_flow,
        'prescription_form': prescription_form,
        'form_state': {
            'blood_pressure': request.POST.get('blood_pressure', '') if request.method == 'POST' else '',
            'temperature': request.POST.get('temperature', '') if request.method == 'POST' else '',
            'heart_rate': request.POST.get('heart_rate', '') if request.method == 'POST' else '',
            'weight': request.POST.get('weight', '') if request.method == 'POST' else '',
            'treatment': request.POST.get('treatment', '') if request.method == 'POST' else '',
            'lab_results': request.POST.get('lab_results', '') if request.method == 'POST' else '',
        },
        'medication_entries_json': json.dumps(_collect_medication_entries(request.POST) if request.method == 'POST' else _collect_medication_entries({})),
    }

    return context


def paginate_queryset(queryset, request, per_page=10):
    """Helper function for pagination"""
    page = request.GET.get('page', 1)
    paginator = Paginator(queryset, per_page)
    
    try:
        paginated_items = paginator.page(page)
    except PageNotAnInteger:
        paginated_items = paginator.page(1)
    except EmptyPage:
        paginated_items = paginator.page(paginator.num_pages)
    
    return paginated_items


@login_required
@role_required('student', 'staff', 'doctor')
def medical_records(request):
    """Display medical records based on user role"""
    # Get records based on user role
    if request.user.role == 'student':
        records = MedicalRecord.objects.filter(student=request.user)
        appointments = Appointment.objects.filter(student=request.user)
    elif request.user.role in ['staff', 'doctor']:
        records = MedicalRecord.objects.filter(doctor=request.user)
        appointments = Appointment.objects.filter(doctor=request.user)
    else:
        records = MedicalRecord.objects.none()
        appointments = Appointment.objects.none()
    
    # Apply filters
    status_filter = request.GET.get('status')
    student_id = request.GET.get('student_id')
    date_from = parse_date(request.GET.get('date_from')) if request.GET.get('date_from') else None
    date_to = parse_date(request.GET.get('date_to')) if request.GET.get('date_to') else None

    if status_filter == 'completed':
        records = records.filter(appointment__status='completed')
    elif status_filter == 'follow_up_required':
        records = records.filter(follow_up_required=True).exclude(appointment__status='completed')
    elif status_filter == 'monitoring':
        records = records.exclude(appointment__status='completed').exclude(follow_up_required=True)
    
    if student_id and request.user.role in ['staff', 'doctor']:
        records = records.filter(student__student_profile__student_id__icontains=student_id)
        appointments = appointments.filter(student__student_profile__student_id__icontains=student_id)
    if date_from:
        records = records.filter(created_at__date__gte=date_from)
        appointments = appointments.filter(date__gte=date_from)
    if date_to:
        records = records.filter(created_at__date__lte=date_to)
        appointments = appointments.filter(date__lte=date_to)

    status_totals = {
        'completed': 0,
        'confirmed': 0,
        'cancelled': 0,
        'pending': 0,
    }
    
    records = records.select_related('student', 'doctor', 'appointment').order_by('-created_at')
    appointments = appointments.exclude(appointment_type='dental').exclude(
        medicalrecord__isnull=False
    ).select_related('student', 'doctor').order_by('-date', '-time')

    timeline_rows = []

    for record in records:
        record_status = record.appointment.status if record.appointment else 'pending'
        if record_status in status_totals:
            status_totals[record_status] += 1

        local_created_at = timezone.localtime(record.created_at) if timezone.is_aware(record.created_at) else record.created_at
        timeline_rows.append({
            'row_type': 'record',
            'record': record,
            'sort_datetime': local_created_at,
        })

    for appointment in appointments:
        if appointment.status in status_totals:
            status_totals[appointment.status] += 1

        local_created_at = timezone.localtime(appointment.created_at) if timezone.is_aware(appointment.created_at) else appointment.created_at
        timeline_rows.append({
            'row_type': 'appointment',
            'appointment': appointment,
            'sort_datetime': local_created_at,
        })

    timeline_rows.sort(key=lambda row: row['sort_datetime'], reverse=True)
    records = paginate_queryset(timeline_rows, request)
    
    context = {
        'records': records,
        'total_count': records.paginator.count if records else 0,
        'status_totals': status_totals,
    }
    
    return render(request, 'medical_records/medical_records.html', context)


@login_required
@role_required('student', 'staff', 'doctor')
def medical_record_detail_page(request, record_id):
    """View detailed medical record page - similar to dental record detail"""
    record = get_object_or_404(MedicalRecord, id=record_id)
    
    # Check permissions
    if request.user.role == 'student' and record.student != request.user:
        messages.error(request, 'Access denied')
        return redirect('medical_records:medical_records')
    elif request.user.role in ['staff', 'doctor'] and record.doctor != request.user:
        messages.error(request, 'Access denied')
        return redirect('medical_records:medical_records')
    
    context = {
        'record': record,
    }
    
    return render(request, 'medical_records/medical_record_detail.html', context)


@login_required
@role_required('student', 'staff', 'doctor')
def medical_record_detail(request, record_id):
    """AJAX/HTMX view to get medical record details for modal display."""
    record = get_object_or_404(MedicalRecord, id=record_id)
    is_htmx = request.headers.get('HX-Request') == 'true'
    
    # Check permissions
    if request.user.role == 'student' and record.student != request.user:
        return JsonResponse({'error': 'Access denied'}, status=403) if not is_htmx else HttpResponse('Access denied', status=403)
    elif request.user.role in ['staff', 'doctor'] and record.doctor != request.user:
        return JsonResponse({'error': 'Access denied'}, status=403) if not is_htmx else HttpResponse('Access denied', status=403)
    
    # Format vital signs for display
    vital_signs_display = []
    if record.vital_signs:
        if record.vital_signs.get('blood_pressure'):
            vital_signs_display.append(f"Blood Pressure: {record.vital_signs['blood_pressure']}")
        if record.vital_signs.get('temperature'):
            vital_signs_display.append(f"Temperature: {record.vital_signs['temperature']}°F")
        if record.vital_signs.get('heart_rate'):
            vital_signs_display.append(f"Heart Rate: {record.vital_signs['heart_rate']} bpm")
        if record.vital_signs.get('weight'):
            vital_signs_display.append(f"Weight: {record.vital_signs['weight']} kg")
    
    html_content = f"""
    <div class="space-y-4">
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
                <h4 class="font-medium text-gray-900 mb-2">Patient Information</h4>
                <div class="bg-gray-50 p-3 rounded-md space-y-1">
                    <p><span class="font-medium">Name:</span> {record.student.get_full_name()}</p>
                    <p><span class="font-medium">Student ID:</span> {getattr(record.student, 'student_profile', None) and record.student.student_profile.student_id or 'N/A'}</p>
                    <p><span class="font-medium">Date:</span> {record.created_at.strftime('%B %d, %Y at %I:%M %p')}</p>
                </div>
            </div>
            <div>
                <h4 class="font-medium text-gray-900 mb-2">Doctor Information</h4>
                <div class="bg-gray-50 p-3 rounded-md space-y-1">
                    <p><span class="font-medium">Doctor:</span> Dr. {record.doctor.get_full_name()}</p>
                    <p><span class="font-medium">Department:</span> {getattr(record.doctor, 'staff_profile', None) and record.doctor.staff_profile.department or 'N/A'}</p>
                    {f'<p><span class="font-medium">Specialization:</span> {record.doctor.staff_profile.specialization}</p>' if getattr(record.doctor, 'staff_profile', None) and record.doctor.staff_profile.specialization else ''}
                </div>
            </div>
        </div>
        
        <div>
            <h4 class="font-medium text-gray-900 mb-2">Diagnosis</h4>
            <div class="bg-gray-50 p-3 rounded-md">
                <p class="text-gray-800">{record.diagnosis}</p>
            </div>
        </div>
        
        <div>
            <h4 class="font-medium text-gray-900 mb-2">Treatment</h4>
            <div class="bg-gray-50 p-3 rounded-md">
                <p class="text-gray-800">{record.treatment}</p>
            </div>
        </div>
        
        {f'''
        <div>
            <h4 class="font-medium text-gray-900 mb-2">Prescription</h4>
            <div class="bg-gray-50 p-3 rounded-md">
                <p class="text-gray-800">{record.prescription_record.prescription_body if hasattr(record, 'prescription_record') and record.prescription_record else 'No prescription recorded'}</p>
            </div>
        </div>
        ''' if hasattr(record, 'prescription_record') and record.prescription_record else ''}
        
        {f'''
        <div>
            <h4 class="font-medium text-gray-900 mb-2">Vital Signs</h4>
            <div class="bg-gray-50 p-3 rounded-md">
                <ul class="list-disc list-inside space-y-1">
                    {''.join([f'<li class="text-gray-800">{sign}</li>' for sign in vital_signs_display])}
                </ul>
            </div>
        </div>
        ''' if vital_signs_display else ''}
        
        {f'''
        <div>
            <h4 class="font-medium text-gray-900 mb-2">Lab Results</h4>
            <div class="bg-gray-50 p-3 rounded-md">
                <p class="text-gray-800">{record.lab_results}</p>
            </div>
        </div>
        ''' if record.lab_results else ''}
        
        <div>
            <h4 class="font-medium text-gray-900 mb-2">Follow-up</h4>
            <div class="bg-gray-50 p-3 rounded-md">
                {f'<p class="text-gray-800">Follow-up required on: {record.follow_up_date.strftime("%B %d, %Y")}</p>' if record.follow_up_required and record.follow_up_date else 
                 '<p class="text-gray-800">Follow-up required: Yes</p>' if record.follow_up_required else 
                 '<p class="text-gray-800">No follow-up required</p>'}
            </div>
        </div>
        
        {f'''
        <div>
            <h4 class="font-medium text-gray-900 mb-2">Related Appointment</h4>
            <div class="bg-gray-50 p-3 rounded-md">
                <p class="text-gray-800">Appointment on {record.appointment.date.strftime("%B %d, %Y")} at {record.appointment.time.strftime("%I:%M %p")}</p>
                <p class="text-sm text-gray-600">Type: {record.appointment.get_appointment_type_display()}</p>
            </div>
        </div>
        ''' if record.appointment else ''}
    </div>
    """
    
    if is_htmx:
        return HttpResponse(html_content)
    return JsonResponse({'html': html_content})


@login_required
def create_medical_record(request, appointment_id):
    if request.user.role not in ['staff', 'doctor']:
        messages.error(request, 'Access denied')
        return redirect('core:dashboard')
    
    appointment = get_object_or_404(Appointment, id=appointment_id, doctor=request.user)

    # General consultation must be confirmed before a medical record can be created.
    if appointment.appointment_type == 'consultation' and appointment.status == 'pending':
        messages.warning(request, 'General consultation appointments must be confirmed first before creating a medical record.')
        return redirect('appointments:appointment_detail', appointment_id=appointment.id)
    
    # Check if medical record already exists
    if MedicalRecord.objects.filter(appointment=appointment).exists():
        messages.warning(request, 'Medical record already exists for this appointment.')
        return redirect('appointments:appointment_detail', appointment_id=appointment.id)

    # Check if dental record already exists for this appointment
    if DentalRecord.objects.filter(appointment=appointment).exists():
        messages.warning(request, 'A dental record already exists for this appointment. Only one record per appointment is allowed.')
        return redirect('appointments:appointment_detail', appointment_id=appointment.id)
    
    prescription_form = PrescriptionPatientForm(request.POST or None, initial=_build_prescription_initial(appointment.student, doctor=appointment.doctor))
    
    if request.method == 'POST':
        diagnosis = request.POST.get('diagnosis', '').strip()
        treatment = request.POST.get('treatment', '').strip()
        lab_results = request.POST.get('lab_results', '').strip()

        # Collect vital signs
        vital_signs = {}
        
        blood_pressure = request.POST.get('blood_pressure', '').strip()
        if blood_pressure:
            vital_signs['blood_pressure'] = blood_pressure
        
        temperature = request.POST.get('temperature', '').strip()
        if temperature:
            vital_signs['temperature'] = temperature
        
        heart_rate = request.POST.get('heart_rate', '').strip()
        if heart_rate:
            try:
                hr_value = int(heart_rate)
                if 40 <= hr_value <= 200:
                    vital_signs['heart_rate'] = heart_rate
                else:
                    messages.error(request, 'Heart rate must be between 40 and 200 bpm.')
                    return render(request, 'medical_records/create_medical_record.html', _build_create_medical_record_context(request, appointment=appointment, prescription_form=prescription_form))
            except ValueError:
                messages.error(request, 'Heart rate must be a valid number.')
                return render(request, 'medical_records/create_medical_record.html', _build_create_medical_record_context(request, appointment=appointment, prescription_form=prescription_form))
        
        weight = request.POST.get('weight', '').strip()
        if weight:
            try:
                weight_value = float(weight)
                if 20.0 <= weight_value <= 300.0:
                    vital_signs['weight'] = weight
                else:
                    messages.error(request, 'Weight must be between 20 and 300 kg.')
                    return render(request, 'medical_records/create_medical_record.html', _build_create_medical_record_context(request, appointment=appointment, prescription_form=prescription_form))
            except ValueError:
                messages.error(request, 'Weight must be a valid number.')
                return render(request, 'medical_records/create_medical_record.html', _build_create_medical_record_context(request, appointment=appointment, prescription_form=prescription_form))
        
        # Validate required fields
        if not diagnosis or not treatment:
            messages.error(request, 'Diagnosis and treatment are required.')
            return render(request, 'medical_records/create_medical_record.html', _build_create_medical_record_context(request, appointment=appointment, prescription_form=prescription_form))
        
        try:
            with transaction.atomic():
                locked_appointment = Appointment.objects.select_for_update().get(pk=appointment.pk)

                if MedicalRecord.objects.filter(appointment=locked_appointment).exists():
                    messages.warning(request, 'Medical record already exists for this appointment.')
                    return redirect('appointments:appointment_detail', appointment_id=locked_appointment.id)

                if DentalRecord.objects.filter(appointment=locked_appointment).exists():
                    messages.warning(request, 'A dental record already exists for this appointment. Only one record per appointment is allowed.')
                    return redirect('appointments:appointment_detail', appointment_id=locked_appointment.id)

                # Create medical record
                medical_record = MedicalRecord.objects.create(
                    student=locked_appointment.student,
                    doctor=request.user,
                    appointment=locked_appointment,
                    diagnosis=diagnosis,
                    treatment=treatment,
                    lab_results=lab_results,
                    vital_signs=vital_signs,
                )

                # Create linked Prescription with structured medication data
                if prescription_form.is_valid() and request.POST.get('diagnosis', '').strip():
                    prescription_obj = prescription_form.save(commit=False)
                    prescription_obj.user = request.user
                    prescription_obj.medical_record = medical_record
                    prescription_obj.status = Prescription.Status.COMPLETED

                    # Build prescription_body from the structured medications
                    diagnosis_val = prescription_form.cleaned_data.get('diagnosis', '')
                    instructions_val = prescription_form.cleaned_data.get('instructions', '')
                    medications_val = request.POST.get('medications', '').strip()
                    body_parts = []
                    if diagnosis_val:
                        body_parts.append(f"Diagnosis:\n{diagnosis_val}")
                    if medications_val:
                        body_parts.append(f"Medications:\n{medications_val}")
                    if instructions_val:
                        body_parts.append(f"Instructions:\n{instructions_val}")
                    prescription_obj.prescription_body = '\n\n'.join(body_parts)
                    prescription_obj.save()

                    # Create PrescriptionItem records from structured medication cards
                    import re
                    med_item_pattern = re.compile(r'^med_item_(\d+)_name$')
                    med_indices = set()
                    for key in request.POST:
                        match = med_item_pattern.match(key)
                        if match:
                            med_indices.add(int(match.group(1)))

                    from health_forms_services.models import PrescriptionItem
                    for idx in sorted(med_indices):
                        name = request.POST.get(f'med_item_{idx}_name', '').strip()
                        if name:
                            PrescriptionItem.objects.create(
                                prescription=prescription_obj,
                                medication_name=name,
                                dosage=request.POST.get(f'med_item_{idx}_dosage', '').strip(),
                                frequency=request.POST.get(f'med_item_{idx}_frequency', '').strip(),
                                duration=request.POST.get(f'med_item_{idx}_duration', '').strip(),
                                quantity=request.POST.get(f'med_item_{idx}_quantity', '').strip(),
                                instructions=request.POST.get(f'med_item_{idx}_instructions', '').strip(),
                            )

                # Update appointment status
                locked_appointment.status = 'completed'
                locked_appointment.save(update_fields=['status', 'updated_at'])
            
            # Create notification for student
            Notification.objects.create(
                user=appointment.student,
                title='Medical Record Created',
                message=f'Your medical record from your appointment on {appointment.date.strftime("%B %d, %Y")} is now available',
                notification_type='general',
                transaction_type='medical_record_created',
                related_id=medical_record.id
            )
            
            messages.success(request, 'Medical record created successfully!')
            return redirect('appointments:appointment_detail', appointment_id=appointment.id)
            
        except Exception:
            messages.error(request, 'An error occurred while creating the medical record. Please try again.')
            return render(request, 'medical_records/create_medical_record.html', _build_create_medical_record_context(request, appointment=appointment, prescription_form=prescription_form))
    
    return render(request, 'medical_records/create_medical_record.html', _build_create_medical_record_context(request, appointment=appointment, prescription_form=prescription_form))


@login_required
@role_required('staff', 'doctor')
def create_medical_record_for_student(request):
    """Create a medical record for a selected student without appointment context."""
    if request.method == 'POST':
        student_id = request.POST.get('student_id')
        diagnosis = request.POST.get('diagnosis', '').strip()
        treatment = request.POST.get('treatment', '').strip()
        lab_results = request.POST.get('lab_results', '').strip()
        follow_up = request.POST.get('follow_up_required') == 'on'
        follow_up_date_str = request.POST.get('follow_up_date') if follow_up else None

        if not student_id:
            messages.error(request, 'Please select a student first.')
            return render(
                request,
                'medical_records/create_medical_record.html',
                _build_create_medical_record_context(request, student=None, is_direct_student_flow=True),
            )

        student = get_object_or_404(User, id=student_id, role='student')
        prescription_form = PrescriptionPatientForm(request.POST or None, initial=_build_prescription_initial(student))

        follow_up_date = None
        if follow_up and follow_up_date_str:
            try:
                follow_up_date = datetime.strptime(follow_up_date_str, '%Y-%m-%d').date()
                if follow_up_date <= timezone.now().date():
                    messages.error(request, 'Follow-up date must be in the future.')
                    return render(
                        request,
                        'medical_records/create_medical_record.html',
                        _build_create_medical_record_context(request, student=student, prescription_form=prescription_form, is_direct_student_flow=True),
                    )
            except ValueError:
                messages.error(request, 'Invalid follow-up date format.')
                return render(
                    request,
                    'medical_records/create_medical_record.html',
                    _build_create_medical_record_context(request, student=student, prescription_form=prescription_form, is_direct_student_flow=True),
                )

        vital_signs = {}

        blood_pressure = request.POST.get('blood_pressure', '').strip()
        if blood_pressure:
            vital_signs['blood_pressure'] = blood_pressure

        temperature = request.POST.get('temperature', '').strip()
        if temperature:
            vital_signs['temperature'] = temperature

        heart_rate = request.POST.get('heart_rate', '').strip()
        if heart_rate:
            try:
                hr_value = int(heart_rate)
                if 40 <= hr_value <= 200:
                    vital_signs['heart_rate'] = heart_rate
                else:
                    messages.error(request, 'Heart rate must be between 40 and 200 bpm.')
                    return render(
                        request,
                        'medical_records/create_medical_record.html',
                        _build_create_medical_record_context(request, student=student, prescription_form=prescription_form, is_direct_student_flow=True),
                    )
            except ValueError:
                messages.error(request, 'Heart rate must be a valid number.')
                return render(
                    request,
                    'medical_records/create_medical_record.html',
                    _build_create_medical_record_context(request, student=student, prescription_form=prescription_form, is_direct_student_flow=True),
                )

        weight = request.POST.get('weight', '').strip()
        if weight:
            try:
                weight_value = float(weight)
                if 20.0 <= weight_value <= 300.0:
                    vital_signs['weight'] = weight
                else:
                    messages.error(request, 'Weight must be between 20 and 300 kg.')
                    return render(
                        request,
                        'medical_records/create_medical_record.html',
                        _build_create_medical_record_context(request, student=student, prescription_form=prescription_form, is_direct_student_flow=True),
                    )
            except ValueError:
                messages.error(request, 'Weight must be a valid number.')
                return render(
                    request,
                    'medical_records/create_medical_record.html',
                    _build_create_medical_record_context(request, student=student, prescription_form=prescription_form, is_direct_student_flow=True),
                )

        if not diagnosis or not treatment:
            messages.error(request, 'Diagnosis and treatment are required.')
            return render(
                request,
                'medical_records/create_medical_record.html',
                _build_create_medical_record_context(request, student=student, prescription_form=prescription_form, is_direct_student_flow=True),
            )

        try:
            with transaction.atomic():
                medical_record = MedicalRecord.objects.create(
                    student=student,
                    doctor=request.user,
                    appointment=None,
                    diagnosis=diagnosis,
                    treatment=treatment,
                    lab_results=lab_results,
                    vital_signs=vital_signs,
                    follow_up_required=follow_up,
                    follow_up_date=follow_up_date,
                )

                # Create linked Prescription with structured medication data
                if prescription_form.is_valid() and request.POST.get('diagnosis', '').strip():
                    prescription_obj = prescription_form.save(commit=False)
                    prescription_obj.user = request.user
                    prescription_obj.medical_record = medical_record
                    prescription_obj.status = Prescription.Status.COMPLETED

                    # Build prescription_body from the structured medications
                    diagnosis_val = prescription_form.cleaned_data.get('diagnosis', '')
                    instructions_val = prescription_form.cleaned_data.get('instructions', '')
                    medications_val = request.POST.get('medications', '').strip()
                    body_parts = []
                    if diagnosis_val:
                        body_parts.append(f"Diagnosis:\n{diagnosis_val}")
                    if medications_val:
                        body_parts.append(f"Medications:\n{medications_val}")
                    if instructions_val:
                        body_parts.append(f"Instructions:\n{instructions_val}")
                    prescription_obj.prescription_body = '\n\n'.join(body_parts)
                    prescription_obj.save()

                    # Create PrescriptionItem records from structured medication cards
                    import re
                    med_item_pattern = re.compile(r'^med_item_(\d+)_name$')
                    med_indices = set()
                    for key in request.POST:
                        match = med_item_pattern.match(key)
                        if match:
                            med_indices.add(int(match.group(1)))

                    from health_forms_services.models import PrescriptionItem
                    for idx in sorted(med_indices):
                        name = request.POST.get(f'med_item_{idx}_name', '').strip()
                        if name:
                            PrescriptionItem.objects.create(
                                prescription=prescription_obj,
                                medication_name=name,
                                dosage=request.POST.get(f'med_item_{idx}_dosage', '').strip(),
                                frequency=request.POST.get(f'med_item_{idx}_frequency', '').strip(),
                                duration=request.POST.get(f'med_item_{idx}_duration', '').strip(),
                                quantity=request.POST.get(f'med_item_{idx}_quantity', '').strip(),
                                instructions=request.POST.get(f'med_item_{idx}_instructions', '').strip(),
                            )

            Notification.objects.create(
                user=student,
                title='Medical Record Created',
                message='A new medical record has been created for you by the clinic.',
                notification_type='general',
                transaction_type='medical_record_created',
                related_id=medical_record.id,
            )

            messages.success(request, 'Medical record created successfully!')
            return redirect('medical_records:medical_record_detail_page', record_id=medical_record.id)
        except Exception:
            messages.error(request, 'An error occurred while creating the medical record. Please try again.')
            return render(
                request,
                'medical_records/create_medical_record.html',
                _build_create_medical_record_context(request, student=student, prescription_form=prescription_form, is_direct_student_flow=True),
            )

    selected_student = None
    student_id = request.GET.get('student')
    if student_id:
        selected_student = get_object_or_404(User, id=student_id, role='student')

    prescription_form = PrescriptionPatientForm(initial=_build_prescription_initial(selected_student))
    return render(request, 'medical_records/create_medical_record.html', _build_create_medical_record_context(request, student=selected_student, prescription_form=prescription_form, is_direct_student_flow=True))


@login_required
@role_required('staff', 'doctor')
def schedule_follow_up(request, record_id):
    """
    HTMX view: returns a follow-up scheduling form for a medical record.
    POST: creates a follow-up appointment for the student.
    """
    record = get_object_or_404(MedicalRecord, id=record_id, doctor=request.user)

    def _inline_error(message):
        return HttpResponse(
            '<div class="flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2">'
            '<svg class="mt-0.5 h-4 w-4 flex-shrink-0 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">'
            '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>'
            '</svg>'
            f'<p class="text-sm text-red-700">{message}</p>'
            '</div>'
        )

    if request.method == 'POST':
        follow_up_date_str = request.POST.get('follow_up_date')
        follow_up_time_str = request.POST.get('follow_up_time')
        follow_up_reason = request.POST.get('follow_up_reason', '').strip()

        if not follow_up_date_str or not follow_up_time_str:
            return _inline_error('Date and time are required.')

        try:
            follow_up_date = datetime.strptime(follow_up_date_str, '%Y-%m-%d').date()
            follow_up_time = datetime.strptime(follow_up_time_str, '%H:%M').time()

            if follow_up_date <= timezone.now().date():
                return _inline_error('Follow-up date must be in the future.')

            # Check for doctor schedule conflict
            from appointments.models import Appointment
            conflict = Appointment.objects.filter(
                doctor=request.user,
                date=follow_up_date,
                time=follow_up_time,
                status__in=['pending', 'confirmed'],
            ).exists()
            if conflict:
                return _inline_error('You already have an appointment scheduled at this date and time. Please choose a different time slot.')

            # Check for student schedule conflict
            student_conflict = Appointment.objects.filter(
                student=record.student,
                date=follow_up_date,
                time=follow_up_time,
                status__in=['pending', 'confirmed'],
            ).exists()
            if student_conflict:
                return _inline_error('The student already has an appointment scheduled at this date and time. Please choose a different time slot.')

            if not follow_up_reason:
                follow_up_reason = f'Follow-up for {record.diagnosis[:50]}'

            # Create follow-up appointment
            appointment_type = record.appointment.appointment_type if record.appointment else 'consultation'
            followup_appointment = Appointment.objects.create(
                student=record.student,
                doctor=request.user,
                appointment_type=appointment_type,
                date=follow_up_date,
                time=follow_up_time,
                reason=follow_up_reason,
                status='confirmed',
            )

            # Update record to mark follow-up as required
            record.follow_up_required = True
            record.follow_up_date = follow_up_date
            record.save(update_fields=['follow_up_required', 'follow_up_date'])

            # Notify student
            Notification.objects.create(
                user=record.student,
                title='Follow-up Appointment Scheduled',
                message=f'A follow-up appointment has been scheduled for {follow_up_date.strftime("%B %d, %Y")} at {follow_up_time.strftime("%I:%M %p")}',
                notification_type='appointment',
                transaction_type='appointment_created',
                related_id=followup_appointment.id,
            )

            # Return a response that closes the modal and refreshes the page
            response = HttpResponse(
                '<div class="text-center py-4">'
                '<div class="flex items-center gap-2 p-4 bg-green-50 border border-green-200 rounded-lg mb-4">'
                '<svg class="w-5 h-5 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">'
                '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>'
                '</svg>'
                '<p class="text-sm text-green-800">Follow-up appointment scheduled successfully!</p>'
                '</div>'
                '</div>'
            )
            response['HX-Trigger'] = '{"close-modal": "", "refresh-list": ""}'
            return response

        except ValueError:
            return _inline_error('Invalid date or time format.')

    # GET: return the form HTML
    from django.template.loader import render_to_string
    html = render_to_string('medical_records/_follow_up_form.html', {
        'min_date': timezone.now().date().isoformat(),
        'post_url': request.path,
    }, request=request)
    return HttpResponse(html)
