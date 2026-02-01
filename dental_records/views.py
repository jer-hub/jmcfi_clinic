"""
Dental Record Views for Jose Maria College Foundation, Inc.
Handles dental record creation, viewing, and management
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction, models
from django.http import JsonResponse, HttpResponseForbidden
from django.core.paginator import Paginator
from django.utils import timezone
from django.contrib.auth import get_user_model

from .models import (
    DentalRecord, DentalExamination, DentalVitalSigns,
    DentalHealthQuestionnaire, DentalSystemsReview,
    DentalHistory, PediatricDentalHistory, DentalChart
)
from .forms import (
    DentalRecordForm, DentalExaminationForm, DentalVitalSignsForm,
    DentalHealthQuestionnaireForm, DentalSystemsReviewForm,
    DentalHistoryForm, PediatricDentalHistoryForm, DentalChartForm
)
from core.decorators import role_required
from appointments.models import Appointment

User = get_user_model()


@login_required
@role_required('admin', 'staff', 'doctor')
def dental_record_list(request):
    """List all dental records with search and filtering"""
    dental_records = DentalRecord.objects.select_related('patient', 'examined_by').all()
    
    # Search functionality
    search_query = request.GET.get('search', '')
    if search_query:
        dental_records = dental_records.filter(
            patient__first_name__icontains=search_query
        ) | dental_records.filter(
            patient__last_name__icontains=search_query
        ) | dental_records.filter(
            patient__email__icontains=search_query
        )
    
    # Filter by date
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    if date_from:
        dental_records = dental_records.filter(date_of_examination__gte=date_from)
    if date_to:
        dental_records = dental_records.filter(date_of_examination__lte=date_to)
    
    # Pagination
    paginator = Paginator(dental_records, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'date_from': date_from,
        'date_to': date_to,
    }
    
    return render(request, 'dental_records/dental_record_list.html', context)


@login_required
@role_required('admin', 'staff', 'doctor')
def dental_record_detail(request, record_id):
    """View detailed dental record"""
    dental_record = get_object_or_404(DentalRecord, pk=record_id)
    
    # Get related records if they exist
    try:
        examination = dental_record.examination
    except DentalExamination.DoesNotExist:
        examination = None
    
    try:
        vital_signs = dental_record.vital_signs
    except DentalVitalSigns.DoesNotExist:
        vital_signs = None
    
    try:
        health_questionnaire = dental_record.health_questionnaire
    except DentalHealthQuestionnaire.DoesNotExist:
        health_questionnaire = None
    
    try:
        systems_review = dental_record.systems_review
    except DentalSystemsReview.DoesNotExist:
        systems_review = None
    
    try:
        dental_history = dental_record.dental_history
    except DentalHistory.DoesNotExist:
        dental_history = None
    
    try:
        pediatric_history = dental_record.pediatric_history
    except PediatricDentalHistory.DoesNotExist:
        pediatric_history = None
    
    # Get dental chart
    dental_chart = dental_record.dental_chart.all()
    
    context = {
        'dental_record': dental_record,
        'examination': examination,
        'vital_signs': vital_signs,
        'health_questionnaire': health_questionnaire,
        'systems_review': systems_review,
        'dental_history': dental_history,
        'pediatric_history': pediatric_history,
        'dental_chart': dental_chart,
    }
    
    return render(request, 'dental_records/dental_record_detail.html', context)


@login_required
@role_required('admin', 'staff', 'doctor')
def dental_record_create(request):
    """Create a new dental record with all sections"""
    preselected_patient_id = request.GET.get('patient')
    appointment_id = request.GET.get('appointment')
    preselected_patient = None
    appointment = None
    
    if preselected_patient_id:
        try:
            preselected_patient = User.objects.get(id=preselected_patient_id)
        except User.DoesNotExist:
            preselected_patient = None
    
    if appointment_id:
        try:
            appointment = Appointment.objects.get(id=appointment_id)
            # If we have an appointment, use its patient
            preselected_patient = appointment.student
        except:
            appointment = None

    if request.method == 'POST':
        form = DentalRecordForm(request.POST)
        
        if form.is_valid():
            try:
                with transaction.atomic():
                    # Create dental record
                    dental_record = form.save()
                    
                    # Set appointment if provided
                    if appointment:
                        dental_record.appointment = appointment
                        dental_record.save()
                    
                    # Create related records (empty initially)
                    DentalExamination.objects.create(dental_record=dental_record)
                    DentalVitalSigns.objects.create(dental_record=dental_record)
                    DentalHealthQuestionnaire.objects.create(dental_record=dental_record)
                    DentalSystemsReview.objects.create(dental_record=dental_record)
                    DentalHistory.objects.create(dental_record=dental_record)
                    
                    messages.success(request, 'Dental record created successfully. You can now fill in the detailed information.')
                    return redirect('dental_records:dental_record_edit', record_id=dental_record.id)
            except Exception as e:
                messages.error(request, f'Error creating dental record: {str(e)}')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        initial_data = {
            'date_of_examination': timezone.now().date(),
            'examined_by': request.user if request.user.role in ['staff', 'doctor'] else None,
            'appointment': appointment,
        }
        
        if preselected_patient:
            initial_data['patient'] = preselected_patient
            # Pre-fill patient data if available
            if hasattr(preselected_patient, 'student_profile') and preselected_patient.student_profile:
                profile = preselected_patient.student_profile
                initial_data.update({
                    'middle_name': profile.middle_name or '',
                    'age': profile.age,
                    'gender': profile.gender,
                    'civil_status': profile.civil_status or 'single',
                    'address': profile.address or '',
                    'date_of_birth': profile.date_of_birth,
                    'place_of_birth': profile.place_of_birth or '',
                    'email': preselected_patient.email,
                    'contact_number': profile.phone or '',
                    'telephone_number': profile.telephone_number or '',
                    'designation': 'student',
                    'department_college_office': profile.department or '',
                    'guardian_name': profile.emergency_contact or '',
                    'guardian_contact': profile.emergency_phone or '',
                })
            elif hasattr(preselected_patient, 'staff_profile') and preselected_patient.staff_profile:
                profile = preselected_patient.staff_profile
                initial_data.update({
                    'middle_name': profile.middle_name or '',
                    'age': profile.age,
                    'gender': profile.gender,
                    'civil_status': profile.civil_status or 'single',
                    'address': profile.address or '',
                    'date_of_birth': profile.date_of_birth,
                    'place_of_birth': profile.place_of_birth or '',
                    'email': preselected_patient.email,
                    'contact_number': profile.phone or '',
                    'telephone_number': profile.telephone_number or '',
                    'designation': 'employee',
                    'department_college_office': profile.department or '',
                    'guardian_name': profile.emergency_contact or '',
                    'guardian_contact': profile.emergency_phone or '',
                })
        
        form = DentalRecordForm(initial=initial_data)
    
    context = {
        'form': form,
        'title': 'Create New Dental Record',
        'preselected_patient': preselected_patient,
        'appointment': appointment,
    }
    
    return render(request, 'dental_records/dental_record_form.html', context)


@login_required
@role_required('admin', 'staff', 'doctor')
def dental_record_edit(request, record_id):
    """Edit comprehensive dental record with all sections"""
    dental_record = get_object_or_404(DentalRecord, pk=record_id)
    
    # Get or create related records
    examination, _ = DentalExamination.objects.get_or_create(dental_record=dental_record)
    vital_signs, _ = DentalVitalSigns.objects.get_or_create(dental_record=dental_record)
    health_questionnaire, _ = DentalHealthQuestionnaire.objects.get_or_create(dental_record=dental_record)
    systems_review, _ = DentalSystemsReview.objects.get_or_create(dental_record=dental_record)
    dental_history, _ = DentalHistory.objects.get_or_create(dental_record=dental_record)
    
    # Check if patient is pediatric (under 18)
    is_pediatric = dental_record.age and dental_record.age < 18
    if is_pediatric:
        pediatric_history, _ = PediatricDentalHistory.objects.get_or_create(dental_record=dental_record)
    else:
        try:
            pediatric_history = dental_record.pediatric_history
        except PediatricDentalHistory.DoesNotExist:
            pediatric_history = None
    
    if request.method == 'POST':
        # Determine which form was submitted
        form_type = request.POST.get('form_type')
        is_htmx = request.headers.get('HX-Request')
        
        if form_type == 'demographics':
            form = DentalRecordForm(request.POST, instance=dental_record)
            if form.is_valid():
                form.save()
                if is_htmx:
                    return JsonResponse({'success': True, 'message': 'Patient demographics updated successfully.'})
                messages.success(request, 'Patient demographics updated successfully.')
                return redirect('dental_records:dental_record_edit', record_id=record_id)
            elif is_htmx:
                return JsonResponse({'success': False, 'errors': form.errors}, status=400)
        
        elif form_type == 'examination':
            form = DentalExaminationForm(request.POST, instance=examination)
            if form.is_valid():
                form.save()
                if is_htmx:
                    return JsonResponse({'success': True, 'message': 'Examination findings updated successfully.'})
                messages.success(request, 'Examination findings updated successfully.')
                return redirect('dental_records:dental_record_edit', record_id=record_id)
            elif is_htmx:
                return JsonResponse({'success': False, 'errors': form.errors}, status=400)
        
        elif form_type == 'vital_signs':
            form = DentalVitalSignsForm(request.POST, instance=vital_signs)
            if form.is_valid():
                form.save()
                if is_htmx:
                    return JsonResponse({'success': True, 'message': 'Vital signs updated successfully.'})
                messages.success(request, 'Vital signs updated successfully.')
                return redirect('dental_records:dental_record_edit', record_id=record_id)
            elif is_htmx:
                return JsonResponse({'success': False, 'errors': form.errors}, status=400)
        
        elif form_type == 'health_questionnaire':
            form = DentalHealthQuestionnaireForm(request.POST, instance=health_questionnaire)
            if form.is_valid():
                form.save()
                if is_htmx:
                    return JsonResponse({'success': True, 'message': 'Health questionnaire updated successfully.'})
                messages.success(request, 'Health questionnaire updated successfully.')
                return redirect('dental_records:dental_record_edit', record_id=record_id)
            elif is_htmx:
                return JsonResponse({'success': False, 'errors': form.errors}, status=400)
        
        elif form_type == 'systems_review':
            form = DentalSystemsReviewForm(request.POST, instance=systems_review)
            if form.is_valid():
                form.save()
                if is_htmx:
                    return JsonResponse({'success': True, 'message': 'Systems review updated successfully.'})
                messages.success(request, 'Systems review updated successfully.')
                return redirect('dental_records:dental_record_edit', record_id=record_id)
            elif is_htmx:
                return JsonResponse({'success': False, 'errors': form.errors}, status=400)
        
        elif form_type == 'dental_history':
            form = DentalHistoryForm(request.POST, instance=dental_history)
            if form.is_valid():
                form.save()
                if is_htmx:
                    return JsonResponse({'success': True, 'message': 'Dental history updated successfully.'})
                messages.success(request, 'Dental history updated successfully.')
                return redirect('dental_records:dental_record_edit', record_id=record_id)
            elif is_htmx:
                return JsonResponse({'success': False, 'errors': form.errors}, status=400)
        
        elif form_type == 'pediatric_history' and is_pediatric:
            form = PediatricDentalHistoryForm(request.POST, instance=pediatric_history)
            if form.is_valid():
                form.save()
                if is_htmx:
                    return JsonResponse({'success': True, 'message': 'Pediatric history updated successfully.'})
                messages.success(request, 'Pediatric history updated successfully.')
                return redirect('dental_records:dental_record_edit', record_id=record_id)
            elif is_htmx:
                return JsonResponse({'success': False, 'errors': form.errors}, status=400)
    
    # Initialize all forms for GET request
    demographics_form = DentalRecordForm(instance=dental_record)
    examination_form = DentalExaminationForm(instance=examination)
    vital_signs_form = DentalVitalSignsForm(instance=vital_signs)
    health_questionnaire_form = DentalHealthQuestionnaireForm(instance=health_questionnaire)
    systems_review_form = DentalSystemsReviewForm(instance=systems_review)
    dental_history_form = DentalHistoryForm(instance=dental_history)
    pediatric_history_form = PediatricDentalHistoryForm(instance=pediatric_history) if is_pediatric else None
    
    # Get dental chart
    dental_chart = dental_record.dental_chart.all().order_by('tooth_number')
    
    context = {
        'dental_record': dental_record,
        'appointment': dental_record.appointment,
        'demographics_form': demographics_form,
        'examination_form': examination_form,
        'vital_signs_form': vital_signs_form,
        'health_questionnaire_form': health_questionnaire_form,
        'systems_review_form': systems_review_form,
        'dental_history_form': dental_history_form,
        'pediatric_history_form': pediatric_history_form,
        'dental_chart': dental_chart,
        'is_pediatric': is_pediatric,
        'title': f'Edit Dental Record - {dental_record.patient.get_full_name()}',
    }
    
    return render(request, 'dental_records/dental_record_edit.html', context)


@login_required
@role_required('admin', 'staff', 'doctor')
def complete_appointment(request, record_id):
    """Mark the associated appointment as completed"""
    dental_record = get_object_or_404(DentalRecord, pk=record_id)
    
    if not dental_record.appointment:
        messages.error(request, 'No appointment associated with this dental record.')
        return redirect('dental_records:dental_record_edit', record_id=record_id)
    
    if dental_record.appointment.status != 'completed':
        dental_record.appointment.status = 'completed'
        dental_record.appointment.save()
        messages.success(request, 'Appointment marked as completed successfully.')
    else:
        messages.info(request, 'Appointment is already completed.')
    
    return redirect('dental_records:dental_record_edit', record_id=record_id)


@login_required
@role_required('admin', 'staff', 'doctor')
def dental_chart_add_tooth(request, record_id):
    """Add or update a tooth in the dental chart"""
    dental_record = get_object_or_404(DentalRecord, pk=record_id)
    
    if request.method == 'POST':
        tooth_number = request.POST.get('tooth_number')
        
        # Check if tooth already exists
        tooth, created = DentalChart.objects.get_or_create(
            dental_record=dental_record,
            tooth_number=tooth_number,
            defaults={
                'tooth_type': request.POST.get('tooth_type', 'permanent'),
                'condition': request.POST.get('condition', 'healthy'),
                'notes': request.POST.get('notes', '')
            }
        )
        
        if not created:
            # Update existing tooth
            tooth.tooth_type = request.POST.get('tooth_type', tooth.tooth_type)
            tooth.condition = request.POST.get('condition', tooth.condition)
            tooth.notes = request.POST.get('notes', tooth.notes)
            tooth.save()
        
        # If HTMX request, return partial template without adding Django messages
        if request.headers.get('HX-Request'):
            dental_chart = dental_record.dental_chart.all().order_by('tooth_number')
            return render(request, 'dental_records/partials/dental_chart_table.html', {
                'dental_chart': dental_chart,
                'dental_record': dental_record,
            })
        
        # Only add messages for non-HTMX requests
        messages.success(request, f'Tooth #{tooth_number} {"added" if created else "updated"} successfully.')
        return redirect('dental_records:dental_record_edit', record_id=record_id)
    
    return redirect('dental_records:dental_record_edit', record_id=record_id)


@login_required
@role_required('admin', 'staff', 'doctor')
def dental_chart_delete_tooth(request, record_id, tooth_id):
    """Remove a tooth from the dental chart"""
    dental_record = get_object_or_404(DentalRecord, pk=record_id)
    tooth = get_object_or_404(DentalChart, pk=tooth_id, dental_record=dental_record)
    
    tooth_number = tooth.tooth_number
    tooth.delete()
    
    # If HTMX request, return partial template without adding Django messages
    if request.headers.get('HX-Request'):
        dental_chart = dental_record.dental_chart.all().order_by('tooth_number')
        return render(request, 'dental_records/partials/dental_chart_table.html', {
            'dental_chart': dental_chart,
            'dental_record': dental_record,
        })
    
    # Only add messages for non-HTMX requests
    messages.success(request, f'Tooth #{tooth_number} removed from chart.')
    return redirect('dental_records:dental_record_edit', record_id=record_id)


@login_required
@role_required('admin', 'staff', 'doctor')
def dental_record_delete(request, record_id):
    """Delete a dental record"""
    dental_record = get_object_or_404(DentalRecord, pk=record_id)
    
    if request.method == 'POST':
        patient_name = dental_record.patient.get_full_name()
        dental_record.delete()
        messages.success(request, f'Dental record for {patient_name} deleted successfully.')
        return redirect('dental_records:dental_record_list')
    
    return redirect('dental_records:dental_record_detail', record_id=record_id)


@login_required
def my_dental_records(request):
    """View dental records for the logged-in patient"""
    dental_records = DentalRecord.objects.filter(patient=request.user).order_by('-date_of_examination')
    
    # Filter out records where appointment is not completed
    accessible_records = []
    for record in dental_records:
        if record.appointment and record.appointment.status != 'completed':
            continue  # Skip this record
        accessible_records.append(record)
    
    context = {
        'dental_records': accessible_records,
    }
    
    return render(request, 'dental_records/my_dental_records.html', context)


@login_required
def my_dental_record_detail(request, record_id):
    """View detailed dental record for the logged-in patient"""
    dental_record = get_object_or_404(DentalRecord, pk=record_id, patient=request.user)
    
    # Check if appointment is completed (if exists)
    if dental_record.appointment and dental_record.appointment.status != 'completed':
        messages.error(request, 'You can only view dental records for completed appointments.')
        return redirect('dental_records:my_dental_records')
    
    # Get related records
    try:
        examination = dental_record.examination
    except DentalExamination.DoesNotExist:
        examination = None
    
    try:
        vital_signs = dental_record.vital_signs
    except DentalVitalSigns.DoesNotExist:
        vital_signs = None
    
    try:
        health_questionnaire = dental_record.health_questionnaire
    except DentalHealthQuestionnaire.DoesNotExist:
        health_questionnaire = None
    
    try:
        systems_review = dental_record.systems_review
    except DentalSystemsReview.DoesNotExist:
        systems_review = None
    
    try:
        dental_history = dental_record.dental_history
    except DentalHistory.DoesNotExist:
        dental_history = None
    
    try:
        pediatric_history = dental_record.pediatric_history
    except PediatricDentalHistory.DoesNotExist:
        pediatric_history = None
    
    dental_chart = dental_record.dental_chart.all()
    
    context = {
        'dental_record': dental_record,
        'examination': examination,
        'vital_signs': vital_signs,
        'health_questionnaire': health_questionnaire,
        'systems_review': systems_review,
        'dental_history': dental_history,
        'pediatric_history': pediatric_history,
        'dental_chart': dental_chart,
    }
    
    return render(request, 'dental_records/my_dental_record_detail.html', context)


@login_required
@role_required('admin', 'staff', 'doctor')
def dental_record_export_json(request, record_id):
    """Export dental record as JSON for AI processing or backup"""
    dental_record = get_object_or_404(DentalRecord, pk=record_id)
    
    # Build comprehensive JSON structure
    data = {
        "demographics": {
            "lastName": dental_record.patient.last_name,
            "firstName": dental_record.patient.first_name,
            "middleName": dental_record.middle_name,
            "age": dental_record.age,
            "gender": dental_record.gender,
            "civilStatus": dental_record.civil_status,
            "address": dental_record.address,
            "dateOfBirth": dental_record.date_of_birth.isoformat() if dental_record.date_of_birth else None,
            "placeOfBirth": dental_record.place_of_birth,
            "email": dental_record.email,
            "contactNumber": dental_record.contact_number,
            "telephoneNumber": dental_record.telephone_number,
            "designation": dental_record.designation,
            "departmentCollegeOffice": dental_record.department_college_office,
            "emergencyContact": {
                "name": dental_record.guardian_name,
                "contactNumber": dental_record.guardian_contact
            },
            "dateOfExamination": dental_record.date_of_examination.isoformat() if dental_record.date_of_examination else None
        }
    }
    
    # Add health questionnaire
    try:
        hq = dental_record.health_questionnaire
        data["healthQuestionnaire"] = {
            "lastHospitalConfinement": {
                "date": hq.last_hospital_date.isoformat() if hq.last_hospital_date else None,
                "reason": hq.last_hospital_reason
            },
            "lastDoctorConsultation": {
                "date": hq.last_doctor_date.isoformat() if hq.last_doctor_date else None,
                "reason": hq.last_doctor_reason
            },
            "doctorCareSupervision": {
                "answer": hq.doctor_care_2years,
                "reason": hq.doctor_care_reason
            },
            "excessiveBleeding": {
                "answer": hq.excessive_bleeding,
                "when": hq.excessive_bleeding_when
            },
            "medicationsLast2Years": {
                "answer": hq.medications_2years,
                "for": hq.medications_for
            },
            "easilyExhausted": hq.easily_exhausted,
            "swollenAnkles": hq.swollen_ankles,
            "moreThan2Pillows": {
                "answer": hq.more_than_2_pillows,
                "why": hq.pillows_reason
            },
            "tumorCancerDiagnosis": {
                "answer": hq.tumor_cancer,
                "when": hq.tumor_cancer_when
            },
            "forWomen": {
                "pregnant": {
                    "answer": hq.is_pregnant,
                    "months": hq.pregnancy_months
                },
                "birthControlPills": {
                    "answer": hq.birth_control_pills,
                    "specify": hq.birth_control_specify
                },
                "anticipatePregnancy": hq.anticipate_pregnancy,
                "havingPeriod": hq.having_period
            }
        }
    except DentalHealthQuestionnaire.DoesNotExist:
        data["healthQuestionnaire"] = {}
    
    # Add systems review
    try:
        sr = dental_record.systems_review
        conditions = []
        for field in sr._meta.fields:
            if isinstance(field, models.BooleanField) and getattr(sr, field.name):
                conditions.append(field.name)
        data["systemsReview"] = conditions
        if sr.allergies:
            data["allergies"] = sr.allergies
        if sr.other_conditions:
            data["otherConditions"] = sr.other_conditions
    except DentalSystemsReview.DoesNotExist:
        data["systemsReview"] = []
    
    # Add vital signs
    try:
        vs = dental_record.vital_signs
        data["vitalSigns"] = {
            "bloodPressure": vs.blood_pressure,
            "pulseRate": vs.pulse_rate,
            "respiratoryRate": vs.respiratory_rate,
            "temperature": vs.temperature,
            "weight": vs.weight,
            "height": vs.height
        }
    except DentalVitalSigns.DoesNotExist:
        data["vitalSigns"] = {}
    
    data["consentSigned"] = dental_record.consent_signed
    data["signatureDate"] = dental_record.consent_date.isoformat() if dental_record.consent_date else None
    
    return JsonResponse(data, json_dumps_params={'indent': 2})


@login_required
@role_required('admin', 'staff', 'doctor')
def search_patients(request):
    """Search for patients by name, email, or ID for autocomplete"""
    query = request.GET.get('q', '').strip()
    
    if len(query) < 2:
        return JsonResponse({'results': []})
    
    # Search users by first name, last name, or email
    patients = User.objects.filter(
        models.Q(first_name__icontains=query) |
        models.Q(last_name__icontains=query) |
        models.Q(email__icontains=query) |
        models.Q(id__icontains=query)
    )[:20]  # Limit to 20 results
    
    results = []
    for patient in patients:
        # Get profile information if available
        profile_info = ""
        try:
            if hasattr(patient, 'studentprofile'):
                profile = patient.studentprofile
                profile_info = f"Student - {profile.course or 'N/A'}"
            elif hasattr(patient, 'staffprofile'):
                profile = patient.staffprofile
                profile_info = f"Staff - {profile.department or 'N/A'}"
        except:
            profile_info = patient.get_role_display() if hasattr(patient, 'get_role_display') else ""
        
        results.append({
            'id': patient.id,
            'text': f"{patient.last_name}, {patient.first_name}",
            'email': patient.email,
            'role': profile_info,
            'display': f"{patient.last_name}, {patient.first_name} - {patient.email} ({profile_info})"
        })
    
    return JsonResponse({'results': results})


@login_required
@role_required('admin', 'staff', 'doctor')
def get_patient_profile(request, patient_id):
    """Get full patient profile data for auto-filling dental forms"""
    patient = get_object_or_404(User, pk=patient_id)
    
    from datetime import date
    
    data = {
        'first_name': patient.first_name,
        'last_name': patient.last_name,
        'email': patient.email,
        'student_id': '',
        'middle_name': '',
        'gender': '',
        'civil_status': '',
        'date_of_birth': '',
        'place_of_birth': '',
        'age': '',
        'address': '',
        'contact_number': '',
        'telephone_number': '',
        'designation': '',
        'department_college_office': '',
        'guardian_name': '',
        'guardian_contact': '',
    }
    
    # Get profile data based on user role
    try:
        if hasattr(patient, 'student_profile'):
            profile = patient.student_profile
            data.update({
                'student_id': profile.student_id or '',
                'middle_name': profile.middle_name or '',
                'gender': profile.gender or '',
                'civil_status': profile.civil_status or '',
                'date_of_birth': profile.date_of_birth.isoformat() if profile.date_of_birth else '',
                'place_of_birth': profile.place_of_birth or '',
                'age': profile.age or '',
                'address': profile.address or '',
                'contact_number': profile.phone or '',
                'telephone_number': profile.telephone_number or '',
                'designation': 'student',
                'department_college_office': f"{profile.course or ''} - {profile.department or ''}".strip(' -'),
                'guardian_name': profile.emergency_contact or '',
                'guardian_contact': profile.emergency_phone or '',
            })
            
            # Calculate age from date of birth if not set
            if profile.date_of_birth and not data['age']:
                today = date.today()
                dob = profile.date_of_birth
                age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
                data['age'] = age
                
        elif hasattr(patient, 'staff_profile'):
            profile = patient.staff_profile
            data.update({
                'student_id': profile.staff_id or '',  # Use staff_id for the student_id field
                'middle_name': profile.middle_name or '',
                'gender': profile.gender or '',
                'civil_status': profile.civil_status or '',
                'date_of_birth': profile.date_of_birth.isoformat() if profile.date_of_birth else '',
                'place_of_birth': profile.place_of_birth or '',
                'age': profile.age or '',
                'address': profile.address or '',
                'contact_number': profile.phone or '',
                'telephone_number': profile.telephone_number or '',
                'designation': 'employee',
                'department_college_office': profile.department or '',
                'guardian_name': profile.emergency_contact or '',
                'guardian_contact': profile.emergency_phone or '',
            })
            
            # Calculate age from date of birth if not set
            if profile.date_of_birth and not data['age']:
                today = date.today()
                dob = profile.date_of_birth
                age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
                data['age'] = age
    except Exception as e:
        # Profile doesn't exist or error occurred
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error fetching profile for patient {patient_id}: {str(e)}")
    
    return JsonResponse(data)
