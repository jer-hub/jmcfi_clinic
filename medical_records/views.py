from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

from .models import MedicalRecord
from management.models import Notification
from appointments.models import Appointment
from core.decorators import role_required


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
def medical_records(request):
    """Display medical records based on user role"""
    # Get records based on user role
    if request.user.role == 'student':
        records = MedicalRecord.objects.filter(student=request.user)
    elif request.user.role in ['staff', 'doctor']:
        records = MedicalRecord.objects.filter(doctor=request.user)
    elif request.user.role == 'admin':
        records = MedicalRecord.objects.all()
    else:
        records = MedicalRecord.objects.none()
    
    # Apply filters
    student_id = request.GET.get('student_id')
    date_from = parse_date(request.GET.get('date_from')) if request.GET.get('date_from') else None
    date_to = parse_date(request.GET.get('date_to')) if request.GET.get('date_to') else None
    
    if student_id and request.user.role in ['staff', 'doctor', 'admin']:
        records = records.filter(student__student_profile__student_id__icontains=student_id)
    if date_from:
        records = records.filter(created_at__date__gte=date_from)
    if date_to:
        records = records.filter(created_at__date__lte=date_to)
    
    records = records.select_related('student', 'doctor', 'appointment').order_by('-created_at')
    records = paginate_queryset(records, request)
    
    context = {
        'records': records,
        'total_count': records.paginator.count if records else 0,
    }
    
    return render(request, 'medical_records/medical_records.html', context)


@login_required
def medical_record_detail_page(request, record_id):
    """View detailed medical record page - similar to dental record detail"""
    record = get_object_or_404(MedicalRecord, id=record_id)
    
    # Check permissions
    if request.user.role == 'student' and record.student != request.user:
        messages.error(request, 'Access denied')
        return redirect('medical_records:medical_records')
    elif request.user.role in ['staff', 'doctor'] and record.doctor != request.user and request.user.role != 'admin':
        messages.error(request, 'Access denied')
        return redirect('medical_records:medical_records')
    
    context = {
        'record': record,
    }
    
    return render(request, 'medical_records/medical_record_detail.html', context)


@login_required
def medical_record_detail(request, record_id):
    """AJAX view to get medical record details for modal display"""
    record = get_object_or_404(MedicalRecord, id=record_id)
    
    # Check permissions
    if request.user.role == 'student' and record.student != request.user:
        return JsonResponse({'error': 'Access denied'}, status=403)
    elif request.user.role in ['staff', 'doctor'] and record.doctor != request.user and request.user.role != 'admin':
        return JsonResponse({'error': 'Access denied'}, status=403)
    
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
                <p class="text-gray-800">{record.prescription}</p>
            </div>
        </div>
        ''' if record.prescription else ''}
        
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
    
    return JsonResponse({'html': html_content})


@login_required
def create_medical_record(request, appointment_id):
    if request.user.role not in ['staff', 'doctor']:
        messages.error(request, 'Access denied')
        return redirect('management:dashboard')
    
    appointment = get_object_or_404(Appointment, id=appointment_id, doctor=request.user)
    
    # Check if medical record already exists
    if MedicalRecord.objects.filter(appointment=appointment).exists():
        messages.warning(request, 'Medical record already exists for this appointment.')
        return redirect('appointments:appointment_detail', appointment_id=appointment.id)
    
    if request.method == 'POST':
        diagnosis = request.POST.get('diagnosis', '').strip()
        treatment = request.POST.get('treatment', '').strip()
        prescription = request.POST.get('prescription', '').strip()
        lab_results = request.POST.get('lab_results', '').strip()
        follow_up = request.POST.get('follow_up_required') == 'on'
        follow_up_date_str = request.POST.get('follow_up_date') if follow_up else None
        
        # Validate follow-up date
        follow_up_date = None
        if follow_up and follow_up_date_str:
            try:
                from datetime import datetime
                follow_up_date = datetime.strptime(follow_up_date_str, '%Y-%m-%d').date()
                if follow_up_date <= timezone.now().date():
                    messages.error(request, 'Follow-up date must be in the future.')
                    return render(request, 'medical_records/create_medical_record.html', {'appointment': appointment})
            except ValueError:
                messages.error(request, 'Invalid follow-up date format.')
                return render(request, 'medical_records/create_medical_record.html', {'appointment': appointment})
        
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
                    return render(request, 'medical_records/create_medical_record.html', {'appointment': appointment})
            except ValueError:
                messages.error(request, 'Heart rate must be a valid number.')
                return render(request, 'medical_records/create_medical_record.html', {'appointment': appointment})
        
        weight = request.POST.get('weight', '').strip()
        if weight:
            try:
                weight_value = float(weight)
                if 20.0 <= weight_value <= 300.0:
                    vital_signs['weight'] = weight
                else:
                    messages.error(request, 'Weight must be between 20 and 300 kg.')
                    return render(request, 'medical_records/create_medical_record.html', {'appointment': appointment})
            except ValueError:
                messages.error(request, 'Weight must be a valid number.')
                return render(request, 'medical_records/create_medical_record.html', {'appointment': appointment})
        
        # Validate required fields
        if not diagnosis or not treatment:
            messages.error(request, 'Diagnosis and treatment are required.')
            return render(request, 'medical_records/create_medical_record.html', {'appointment': appointment})
        
        try:
            # Create medical record
            medical_record = MedicalRecord.objects.create(
                student=appointment.student,
                doctor=request.user,
                appointment=appointment,
                diagnosis=diagnosis,
                treatment=treatment,
                prescription=prescription,
                lab_results=lab_results,
                vital_signs=vital_signs,
                follow_up_required=follow_up,
                follow_up_date=follow_up_date
            )
            
            # Update appointment status
            appointment.status = 'completed'
            appointment.save()
            
            # Create notification for student
            Notification.objects.create(
                user=appointment.student,
                title='Medical Record Created',
                message=f'Your medical record from your appointment on {appointment.date.strftime("%B %d, %Y")} is now available',
                notification_type='general'
            )
            
            messages.success(request, 'Medical record created successfully!')
            return redirect('appointments:appointment_detail', appointment_id=appointment.id)
            
        except Exception as e:
            messages.error(request, 'An error occurred while creating the medical record. Please try again.')
            return render(request, 'medical_records/create_medical_record.html', {'appointment': appointment})
    
    return render(request, 'medical_records/create_medical_record.html', {'appointment': appointment})
