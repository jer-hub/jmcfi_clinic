from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse
from django.db.models import Q
from django.core.paginator import Paginator
from datetime import datetime, timedelta
from .models import (
    Appointment, MedicalRecord, CertificateRequest, 
    HealthTip, Notification, Feedback, StudentProfile, StaffProfile
)
from django.contrib.auth import get_user_model

User = get_user_model()

# Authentication Views
def login_view(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        
        try:
            user = User.objects.get(email=email)
            user = authenticate(request, username=user.username, password=password)
            if user:
                login(request, user)
                return redirect('management:dashboard')
            else:
                messages.error(request, 'Invalid credentials')
        except User.DoesNotExist:
            messages.error(request, 'User not found')
    
    return render(request, 'management/login.html')

@login_required
def logout_view(request):
    logout(request)
    return redirect('management:login')

@login_required
def dashboard(request):
    context = {}
    
    if request.user.role == 'student':
        context.update({
            'upcoming_appointments': Appointment.objects.filter(
                student=request.user, 
                date__gte=timezone.now().date(),
                status__in=['pending', 'confirmed']
            ).order_by('date', 'time')[:3],
            'recent_records': MedicalRecord.objects.filter(
                student=request.user
            ).order_by('-created_at')[:3],
            'unread_notifications': Notification.objects.filter(
                user=request.user, 
                is_read=False
            ).count(),
            'pending_certificates': CertificateRequest.objects.filter(
                student=request.user,
                status='pending'
            ).count(),
            'total_appointments': Appointment.objects.filter(student=request.user).count(),
            'total_records': MedicalRecord.objects.filter(student=request.user).count(),
            'approved_certificates': CertificateRequest.objects.filter(
                student=request.user,
                status='approved'
            ).count(),
        })
    
    elif request.user.role == 'staff':
        today = timezone.now().date()
        context.update({
            'today_appointments': Appointment.objects.filter(
                doctor=request.user,
                date=today
            ).order_by('time'),
            'pending_appointments': Appointment.objects.filter(
                doctor=request.user,
                status='pending'
            ).count(),
            'pending_certificates': CertificateRequest.objects.filter(
                status='pending'
            ).count(),
            'total_patients': MedicalRecord.objects.filter(
                doctor=request.user
            ).values('student').distinct().count(),
            'completed_appointments': Appointment.objects.filter(
                doctor=request.user,
                status='completed'
            ).count(),
            'recent_records': MedicalRecord.objects.filter(
                doctor=request.user
            ).order_by('-created_at')[:5],
        })
    
    elif request.user.role == 'admin':
        today = timezone.now().date()
        context.update({
            'total_students': User.objects.filter(role='student').count(),
            'total_staff': User.objects.filter(role='staff').count(),
            'total_appointments': Appointment.objects.filter(date=today).count(),
            'pending_certificates': CertificateRequest.objects.filter(
                status='pending'
            ).count(),
            'recent_appointments': Appointment.objects.filter(
                date=today
            ).order_by('-created_at')[:5],
            'recent_feedbacks': Feedback.objects.all().order_by('-created_at')[:5],
            'system_stats': {
                'total_appointments_all': Appointment.objects.count(),
                'total_records': MedicalRecord.objects.count(),
                'total_certificates': CertificateRequest.objects.count(),
                'total_health_tips': HealthTip.objects.filter(is_active=True).count(),
            }
        })
    
    return render(request, 'management/dashboard.html', context)

@login_required
def appointment_list(request):
    if request.user.role == 'student':
        appointments = Appointment.objects.filter(student=request.user)
    elif request.user.role == 'staff':
        appointments = Appointment.objects.filter(doctor=request.user)
    elif request.user.role == 'admin':
        appointments = Appointment.objects.all()
    else:
        appointments = Appointment.objects.none()
    
    # Apply filters
    status = request.GET.get('status')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    if status:
        appointments = appointments.filter(status=status)
    
    if date_from:
        try:
            from datetime import datetime
            date_from_parsed = datetime.strptime(date_from, '%Y-%m-%d').date()
            appointments = appointments.filter(date__gte=date_from_parsed)
        except ValueError:
            pass
    
    if date_to:
        try:
            from datetime import datetime
            date_to_parsed = datetime.strptime(date_to, '%Y-%m-%d').date()
            appointments = appointments.filter(date__lte=date_to_parsed)
        except ValueError:
            pass
    
    appointments = appointments.order_by('-date', '-time')
    
    paginator = Paginator(appointments, 10)
    page = request.GET.get('page')
    appointments = paginator.get_page(page)
    
    return render(request, 'management/appointment_list.html', {'appointments': appointments})

@login_required
def schedule_appointment(request):
    if request.user.role != 'student':
        messages.error(request, 'Only students can schedule appointments')
        return redirect('management:dashboard')
    
    if request.method == 'POST':
        doctor_id = request.POST.get('doctor')
        appointment_type = request.POST.get('appointment_type')
        date = request.POST.get('date')
        time = request.POST.get('time')
        reason = request.POST.get('reason')
        
        # Validation
        if not all([doctor_id, appointment_type, date, time, reason]):
            messages.error(request, 'All fields are required.')
            doctors = User.objects.filter(role='staff').select_related('staff_profile')
            return render(request, 'management/schedule_appointment.html', {'doctors': doctors})
        
        try:
            from datetime import datetime
            appointment_date = datetime.strptime(date, '%Y-%m-%d').date()
            appointment_time = datetime.strptime(time, '%H:%M').time()
            
            # Check if date is not in the past
            if appointment_date < timezone.now().date():
                messages.error(request, 'Cannot schedule appointments for past dates.')
                doctors = User.objects.filter(role='staff').select_related('staff_profile')
                return render(request, 'management/schedule_appointment.html', {'doctors': doctors})
            
            # Check if it's a weekend
            if appointment_date.weekday() >= 5:  # Saturday = 5, Sunday = 6
                messages.error(request, 'Appointments are not available on weekends.')
                doctors = User.objects.filter(role='staff').select_related('staff_profile')
                return render(request, 'management/schedule_appointment.html', {'doctors': doctors})
            
            doctor = User.objects.get(id=doctor_id, role='staff')
            
            # Check for conflicts
            existing_appointment = Appointment.objects.filter(
                doctor=doctor,
                date=appointment_date,
                time=appointment_time,
                status__in=['pending', 'confirmed']
            ).exists()
            
            if existing_appointment:
                messages.error(request, 'This time slot is already booked. Please choose a different time.')
                doctors = User.objects.filter(role='staff').select_related('staff_profile')
                return render(request, 'management/schedule_appointment.html', {'doctors': doctors})
            
            appointment = Appointment.objects.create(
                student=request.user,
                doctor=doctor,
                appointment_type=appointment_type,
                date=appointment_date,
                time=appointment_time,
                reason=reason
            )
            
            # Create notification for doctor
            Notification.objects.create(
                user=doctor,
                title='New Appointment Request',
                message=f'New appointment request from {request.user.get_full_name()} for {appointment_date.strftime("%B %d, %Y")} at {appointment_time.strftime("%I:%M %p")}',
                notification_type='appointment'
            )
            
            # Create notification for student
            Notification.objects.create(
                user=request.user,
                title='Appointment Scheduled',
                message=f'Your appointment with Dr. {doctor.get_full_name()} has been scheduled for {appointment_date.strftime("%B %d, %Y")} at {appointment_time.strftime("%I:%M %p")}',
                notification_type='appointment'
            )
            
            messages.success(request, 'Appointment scheduled successfully!')
            return redirect('management:appointment_list')
            
        except User.DoesNotExist:
            messages.error(request, 'Invalid doctor selected')
        except ValueError:
            messages.error(request, 'Invalid date or time format')
        except Exception as e:
            messages.error(request, 'An error occurred while scheduling the appointment. Please try again.')
    
    doctors = User.objects.filter(role='staff').select_related('staff_profile')
    return render(request, 'management/schedule_appointment.html', {'doctors': doctors})

@login_required
def appointment_detail(request, appointment_id):
    appointment = get_object_or_404(Appointment, id=appointment_id)
    
    # Check permissions
    if request.user.role == 'student' and appointment.student != request.user:
        messages.error(request, 'Access denied')
        return redirect('management:appointment_list')
    elif request.user.role == 'staff' and appointment.doctor != request.user and request.user.role != 'admin':
        messages.error(request, 'Access denied')
        return redirect('management:appointment_list')
    
    if request.method == 'POST':
        if request.user.role in ['staff', 'admin']:
            status = request.POST.get('status')
            notes = request.POST.get('notes')
            
            if status:
                appointment.status = status
            if notes is not None:  # Allow empty notes
                appointment.notes = notes
            appointment.save()
            
            # Create notification for student
            Notification.objects.create(
                user=appointment.student,
                title='Appointment Update',
                message=f'Your appointment status has been updated to {appointment.get_status_display()}',
                notification_type='appointment'
            )
            
            messages.success(request, 'Appointment updated successfully!')
            
        elif request.user.role == 'student' and appointment.student == request.user:
            # Allow students to cancel their own appointments
            status = request.POST.get('status')
            if status == 'cancelled' and appointment.status in ['pending', 'confirmed']:
                appointment.status = 'cancelled'
                appointment.save()
                
                # Create notification for doctor
                Notification.objects.create(
                    user=appointment.doctor,
                    title='Appointment Cancelled',
                    message=f'Appointment with {request.user.get_full_name()} has been cancelled',
                    notification_type='appointment'
                )
                
                messages.success(request, 'Appointment cancelled successfully!')
            else:
                messages.error(request, 'Cannot cancel this appointment')
        
        return redirect('management:appointment_detail', appointment_id=appointment.id)
    
    return render(request, 'management/appointment_detail.html', {'appointment': appointment})

# Medical Records Views
@login_required
def medical_records(request):
    if request.user.role == 'student':
        records = MedicalRecord.objects.filter(student=request.user)
    elif request.user.role == 'staff':
        records = MedicalRecord.objects.filter(doctor=request.user)
    elif request.user.role == 'admin':
        records = MedicalRecord.objects.all()
    else:
        records = MedicalRecord.objects.none()
    
    # Apply filters
    student_id = request.GET.get('student_id')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    if student_id and request.user.role in ['staff', 'admin']:
        records = records.filter(student__student_profile__student_id__icontains=student_id)
    
    if date_from:
        try:
            from datetime import datetime
            date_from = datetime.strptime(date_from, '%Y-%m-%d').date()
            records = records.filter(created_at__date__gte=date_from)
        except ValueError:
            pass
    
    if date_to:
        try:
            from datetime import datetime
            date_to = datetime.strptime(date_to, '%Y-%m-%d').date()
            records = records.filter(created_at__date__lte=date_to)
        except ValueError:
            pass
    
    records = records.select_related('student', 'doctor', 'appointment').order_by('-created_at')
    
    paginator = Paginator(records, 10)
    page = request.GET.get('page')
    records = paginator.get_page(page)
    
    context = {
        'records': records,
        'total_count': records.paginator.count if records else 0,
    }
    
    return render(request, 'management/medical_records.html', context)

@login_required
def medical_record_detail(request, record_id):
    """AJAX view to get medical record details for modal display"""
    record = get_object_or_404(MedicalRecord, id=record_id)
    
    # Check permissions
    if request.user.role == 'student' and record.student != request.user:
        return JsonResponse({'error': 'Access denied'}, status=403)
    elif request.user.role == 'staff' and record.doctor != request.user and request.user.role != 'admin':
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
    if request.user.role != 'staff':
        messages.error(request, 'Access denied')
        return redirect('management:dashboard')
    
    appointment = get_object_or_404(Appointment, id=appointment_id, doctor=request.user)
    
    # Check if medical record already exists
    if hasattr(appointment, 'medicalrecord'):
        messages.warning(request, 'Medical record already exists for this appointment.')
        return redirect('management:appointment_detail', appointment_id=appointment.id)
    
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
                    return render(request, 'management/create_medical_record.html', {'appointment': appointment})
            except ValueError:
                messages.error(request, 'Invalid follow-up date format.')
                return render(request, 'management/create_medical_record.html', {'appointment': appointment})
        
        # Collect and validate vital signs
        vital_signs = {}
        
        blood_pressure = request.POST.get('blood_pressure', '').strip()
        if blood_pressure:
            vital_signs['blood_pressure'] = blood_pressure
        
        temperature = request.POST.get('temperature', '').strip()
        if temperature:
            try:
                temp_value = float(temperature)
                if 90.0 <= temp_value <= 110.0:  # Reasonable range for temperature in Fahrenheit
                    vital_signs['temperature'] = temperature
                else:
                    messages.error(request, 'Temperature must be between 90°F and 110°F.')
                    return render(request, 'management/create_medical_record.html', {'appointment': appointment})
            except ValueError:
                messages.error(request, 'Temperature must be a valid number.')
                return render(request, 'management/create_medical_record.html', {'appointment': appointment})
        
        heart_rate = request.POST.get('heart_rate', '').strip()
        if heart_rate:
            try:
                hr_value = int(heart_rate)
                if 40 <= hr_value <= 200:  # Reasonable range for heart rate
                    vital_signs['heart_rate'] = heart_rate
                else:
                    messages.error(request, 'Heart rate must be between 40 and 200 bpm.')
                    return render(request, 'management/create_medical_record.html', {'appointment': appointment})
            except ValueError:
                messages.error(request, 'Heart rate must be a valid number.')
                return render(request, 'management/create_medical_record.html', {'appointment': appointment})
        
        weight = request.POST.get('weight', '').strip()
        if weight:
            try:
                weight_value = float(weight)
                if 20.0 <= weight_value <= 300.0:  # Reasonable range for weight in kg
                    vital_signs['weight'] = weight
                else:
                    messages.error(request, 'Weight must be between 20 and 300 kg.')
                    return render(request, 'management/create_medical_record.html', {'appointment': appointment})
            except ValueError:
                messages.error(request, 'Weight must be a valid number.')
                return render(request, 'management/create_medical_record.html', {'appointment': appointment})
        
        # Validate required fields
        if not diagnosis or not treatment:
            messages.error(request, 'Diagnosis and treatment are required.')
            return render(request, 'management/create_medical_record.html', {'appointment': appointment})
        
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
            return redirect('management:appointment_detail', appointment_id=appointment.id)
            
        except Exception as e:
            messages.error(request, 'An error occurred while creating the medical record. Please try again.')
            return render(request, 'management/create_medical_record.html', {'appointment': appointment})
    
    return render(request, 'management/create_medical_record.html', {'appointment': appointment})

# Certificate Request Views
@login_required
def certificate_requests(request):
    if request.user.role == 'student':
        requests = CertificateRequest.objects.filter(student=request.user)
    elif request.user.role in ['staff', 'admin']:
        requests = CertificateRequest.objects.all()
    else:
        requests = CertificateRequest.objects.none()
    
    # Apply filters
    status = request.GET.get('status')
    certificate_type = request.GET.get('type')
    
    if status:
        requests = requests.filter(status=status)
    
    if certificate_type:
        requests = requests.filter(certificate_type=certificate_type)
    
    requests = requests.order_by('-created_at')
    
    paginator = Paginator(requests, 10)
    page = request.GET.get('page')
    requests = paginator.get_page(page)
    
    # Get counts for filtering
    total_count = CertificateRequest.objects.filter(
        student=request.user if request.user.role == 'student' else None
    ).count() if request.user.role == 'student' else CertificateRequest.objects.count()
    
    pending_count = CertificateRequest.objects.filter(
        student=request.user if request.user.role == 'student' else None,
        status='pending'
    ).count() if request.user.role == 'student' else CertificateRequest.objects.filter(status='pending').count()
    
    context = {
        'requests': requests,
        'total_count': total_count,
        'pending_count': pending_count,
        'current_status': status,
        'current_type': certificate_type,
        'certificate_types': CertificateRequest.CERTIFICATE_TYPES,
        'status_choices': CertificateRequest.STATUS_CHOICES,
    }
    
    return render(request, 'management/certificate_requests.html', context)

@login_required
def request_certificate(request):
    if request.user.role != 'student':
        messages.error(request, 'Only students can request certificates')
        return redirect('management:dashboard')
    
    if request.method == 'POST':
        certificate_type = request.POST.get('certificate_type')
        purpose = request.POST.get('purpose')
        additional_info = request.POST.get('additional_info', '')
        
        # Validation
        if not certificate_type or not purpose:
            messages.error(request, 'Please fill in all required fields.')
            return render(request, 'management/request_certificate.html')
        
        # Check if certificate type is valid
        valid_types = [choice[0] for choice in CertificateRequest.CERTIFICATE_TYPES]
        if certificate_type not in valid_types:
            messages.error(request, 'Invalid certificate type selected.')
            return render(request, 'management/request_certificate.html')
        
        # Check for recent duplicate requests
        recent_request = CertificateRequest.objects.filter(
            student=request.user,
            certificate_type=certificate_type,
            created_at__gte=timezone.now() - timedelta(days=7),
            status__in=['pending', 'approved']
        ).first()
        
        if recent_request:
            messages.warning(request, 'You already have a recent request for this certificate type. Please wait for it to be processed.')
            return redirect('management:certificate_requests')
        
        # Create the certificate request
        cert_request = CertificateRequest.objects.create(
            student=request.user,
            certificate_type=certificate_type,
            purpose=purpose,
            additional_info=additional_info
        )
        
        # Create notification for staff/admin
        staff_users = User.objects.filter(role__in=['staff', 'admin'])
        for staff in staff_users:
            Notification.objects.create(
                user=staff,
                title='New Certificate Request',
                message=f'{request.user.get_full_name()} has requested a {dict(CertificateRequest.CERTIFICATE_TYPES)[certificate_type]}',
                notification_type='certificate'
            )
        
        messages.success(request, 'Certificate request submitted successfully! You will be notified when it\'s processed.')
        return redirect('management:certificate_requests')
    
    context = {
        'certificate_types': CertificateRequest.CERTIFICATE_TYPES,
    }
    
    return render(request, 'management/request_certificate.html', context)

@login_required
def process_certificate(request, request_id):
    if request.user.role not in ['staff', 'admin']:
        messages.error(request, 'Access denied')
        return redirect('management:dashboard')
    
    cert_request = get_object_or_404(CertificateRequest, id=request_id)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        rejection_reason = request.POST.get('rejection_reason', '')
        
        if action == 'approve':
            cert_request.status = 'approved'
            cert_request.processed_by = request.user
            message = 'Certificate request approved successfully!'
            
            # Create notification for student
            Notification.objects.create(
                user=cert_request.student,
                title='Certificate Request Approved',
                message=f'Your {dict(CertificateRequest.CERTIFICATE_TYPES)[cert_request.certificate_type]} request has been approved and is being prepared.',
                notification_type='certificate'
            )
            
        elif action == 'reject':
            if not rejection_reason:
                messages.error(request, 'Please provide a reason for rejection.')
                return render(request, 'management/process_certificate.html', {'cert_request': cert_request})
                
            cert_request.status = 'rejected'
            cert_request.rejection_reason = rejection_reason
            cert_request.processed_by = request.user
            message = 'Certificate request rejected.'
            
            # Create notification for student
            Notification.objects.create(
                user=cert_request.student,
                title='Certificate Request Rejected',
                message=f'Your {dict(CertificateRequest.CERTIFICATE_TYPES)[cert_request.certificate_type]} request has been rejected. Reason: {rejection_reason}',
                notification_type='certificate'
            )
            
        elif action == 'ready':
            cert_request.status = 'ready'
            cert_request.processed_by = request.user
            message = 'Certificate marked as ready for collection.'
            
            # Create notification for student
            Notification.objects.create(
                user=cert_request.student,
                title='Certificate Ready',
                message=f'Your {dict(CertificateRequest.CERTIFICATE_TYPES)[cert_request.certificate_type]} is ready for collection at the clinic.',
                notification_type='certificate'
            )
        else:
            messages.error(request, 'Invalid action.')
            return render(request, 'management/process_certificate.html', {'cert_request': cert_request})
        
        cert_request.save()
        messages.success(request, message)
        return redirect('management:certificate_requests')
    
    return render(request, 'management/process_certificate.html', {'cert_request': cert_request})

@login_required
def view_certificate(request, request_id):
    """View a certificate in printable format"""
    cert_request = get_object_or_404(CertificateRequest, id=request_id)
    
    # Check permissions - students can only view their own certificates
    if request.user.role == 'student' and cert_request.student != request.user:
        messages.error(request, 'Access denied')
        return redirect('management:certificate_requests')
    
    # Only allow viewing of approved or ready certificates
    if cert_request.status not in ['approved', 'ready']:
        messages.error(request, 'Certificate is not ready for viewing')
        return redirect('management:certificate_requests')
    
    # Prepare certificate data
    context = {
        'cert_request': cert_request,
        'issue_date': timezone.now().date(),
        'certificate_number': f"JMCFI-{cert_request.id:06d}",
    }
    
    return render(request, 'management/view_certificate.html', context)

@login_required 
def print_certificate(request, request_id):
    """Print a certificate - returns a print-optimized view"""
    cert_request = get_object_or_404(CertificateRequest, id=request_id)
    
    # Check permissions
    if request.user.role == 'student' and cert_request.student != request.user:
        messages.error(request, 'Access denied')
        return redirect('management:certificate_requests')
    
    # Only allow printing of ready certificates
    if cert_request.status != 'ready':
        messages.error(request, 'Certificate is not ready for printing')
        return redirect('management:certificate_requests')
    
    # Prepare certificate data
    context = {
        'cert_request': cert_request,
        'issue_date': timezone.now().date(),
        'certificate_number': f"JMCFI-{cert_request.id:06d}",
    }
    
    return render(request, 'management/print_certificate.html', context)

# Health Tips Views
@login_required
def health_tips(request):
    # Show active tips to all users, but also show drafts to their creators
    if request.user.role == 'staff':
        tips = HealthTip.objects.filter(
            Q(is_active=True) | Q(created_by=request.user)
        ).select_related('created_by').distinct()
    else:
        tips = HealthTip.objects.filter(is_active=True).select_related('created_by')
    
    category = request.GET.get('category')
    search = request.GET.get('search')
    
    if category:
        tips = tips.filter(category=category)
    
    if search:
        tips = tips.filter(
            Q(title__icontains=search) | 
            Q(content__icontains=search)
        )
    
    tips = tips.order_by('-created_at')
    
    paginator = Paginator(tips, 9)
    page = request.GET.get('page')
    tips = paginator.get_page(page)
    
    context = {
        'tips': tips,
        'categories': HealthTip.CATEGORY_CHOICES,
        'current_category': category,
        'search_query': search,
        'total_count': tips.paginator.count if tips else 0,
    }
    
    return render(request, 'management/health_tips.html', context)

@login_required
def create_health_tip(request):
    if request.user.role != 'staff':
        messages.error(request, 'Only staff members can create health tips')
        return redirect('management:dashboard')
    
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        content = request.POST.get('content', '').strip()
        category = request.POST.get('category', '').strip()
        status = request.POST.get('status', 'published')  # published or draft
        
        # Validation
        errors = []
        if not title:
            errors.append('Title is required')
        elif len(title) > 200:
            errors.append('Title must be less than 200 characters')
        
        if not content:
            errors.append('Content is required')
        elif len(content) < 50:
            errors.append('Content must be at least 50 characters')
        
        if not category:
            errors.append('Category is required')
        elif category not in [choice[0] for choice in HealthTip.CATEGORY_CHOICES]:
            errors.append('Invalid category selected')
        
        if errors:
            for error in errors:
                messages.error(request, error)
            return render(request, 'management/create_health_tip.html', {
                'title': title,
                'content': content,
                'category': category,
            })
        
        # Create health tip
        health_tip = HealthTip.objects.create(
            title=title,
            content=content,
            category=category,
            created_by=request.user,
            is_active=(status == 'published')
        )
        
        if status == 'published':
            messages.success(request, f'Health tip "{title}" has been published successfully!')
        else:
            messages.success(request, f'Health tip "{title}" has been saved as draft.')
        
        return redirect('management:health_tips')
    
    return render(request, 'management/create_health_tip.html')

@login_required
def edit_health_tip(request, tip_id):
    if request.user.role != 'staff':
        messages.error(request, 'Only staff members can edit health tips')
        return redirect('management:dashboard')
    
    health_tip = get_object_or_404(HealthTip, id=tip_id, created_by=request.user)
    
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        content = request.POST.get('content', '').strip()
        category = request.POST.get('category', '').strip()
        status = request.POST.get('status', 'published')  # published or draft
        
        # Validation
        errors = []
        if not title:
            errors.append('Title is required')
        elif len(title) > 200:
            errors.append('Title must be less than 200 characters')
        
        if not content:
            errors.append('Content is required')
        elif len(content) < 50:
            errors.append('Content must be at least 50 characters')
        
        if not category:
            errors.append('Category is required')
        elif category not in [choice[0] for choice in HealthTip.CATEGORY_CHOICES]:
            errors.append('Invalid category selected')
        
        if errors:
            for error in errors:
                messages.error(request, error)
            return render(request, 'management/edit_health_tip.html', {
                'health_tip': health_tip,
                'title': title,
                'content': content,
                'category': category,
            })
        
        # Update health tip
        health_tip.title = title
        health_tip.content = content
        health_tip.category = category
        health_tip.is_active = (status == 'published')
        health_tip.save()
        
        if status == 'published':
            messages.success(request, f'Health tip "{title}" has been updated and published successfully!')
        else:
            messages.success(request, f'Health tip "{title}" has been updated and saved as draft.')
        
        return redirect('management:health_tips')
    
    return render(request, 'management/edit_health_tip.html', {'health_tip': health_tip})

@login_required
def delete_health_tip(request, tip_id):
    if request.user.role != 'staff':
        messages.error(request, 'Only staff members can delete health tips')
        return redirect('management:dashboard')
    
    health_tip = get_object_or_404(HealthTip, id=tip_id, created_by=request.user)
    
    if request.method == 'POST':
        title = health_tip.title
        health_tip.delete()
        messages.success(request, f'Health tip "{title}" has been deleted successfully.')
        return redirect('management:health_tips')
    
    return render(request, 'management/delete_health_tip.html', {'health_tip': health_tip})

@login_required
def toggle_health_tip_status(request, tip_id):
    if request.user.role != 'staff':
        messages.error(request, 'Only staff members can toggle health tip status')
        return redirect('management:dashboard')
    
    health_tip = get_object_or_404(HealthTip, id=tip_id, created_by=request.user)
    
    if request.method == 'POST':
        health_tip.is_active = not health_tip.is_active
        health_tip.save()
        
        status_text = 'published' if health_tip.is_active else 'unpublished'
        messages.success(request, f'Health tip "{health_tip.title}" has been {status_text}.')
    
    return redirect('management:health_tips')

@login_required
def edit_health_tip(request, tip_id):
    if request.user.role != 'staff':
        messages.error(request, 'Only staff members can edit health tips')
        return redirect('management:dashboard')
    
    health_tip = get_object_or_404(HealthTip, id=tip_id, created_by=request.user)
    
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        content = request.POST.get('content', '').strip()
        category = request.POST.get('category', '').strip()
        status = request.POST.get('status', 'published')
        
        # Validation
        errors = []
        if not title:
            errors.append('Title is required')
        elif len(title) > 200:
            errors.append('Title must be less than 200 characters')
        
        if not content:
            errors.append('Content is required')
        elif len(content) < 50:
            errors.append('Content must be at least 50 characters')
        
        if not category:
            errors.append('Category is required')
        elif category not in [choice[0] for choice in HealthTip.CATEGORY_CHOICES]:
            errors.append('Invalid category selected')
        
        if errors:
            for error in errors:
                messages.error(request, error)
            return render(request, 'management/edit_health_tip.html', {
                'health_tip': health_tip,
                'title': title,
                'content': content,
                'category': category,
            })
        
        # Update health tip
        health_tip.title = title
        health_tip.content = content
        health_tip.category = category
        health_tip.is_active = (status == 'published')
        health_tip.save()
        
        if status == 'published':
            messages.success(request, f'Health tip "{title}" has been updated and published!')
        else:
            messages.success(request, f'Health tip "{title}" has been updated and saved as draft.')
        
        return redirect('management:health_tips')
    
    return render(request, 'management/edit_health_tip.html', {'health_tip': health_tip})

@login_required
def delete_health_tip(request, tip_id):
    if request.user.role != 'staff':
        messages.error(request, 'Only staff members can delete health tips')
        return redirect('management:dashboard')
    
    health_tip = get_object_or_404(HealthTip, id=tip_id, created_by=request.user)
    
    if request.method == 'POST':
        title = health_tip.title
        health_tip.delete()
        messages.success(request, f'Health tip "{title}" has been deleted successfully.')
        return redirect('management:health_tips')
    
    return render(request, 'management/delete_health_tip.html', {'health_tip': health_tip})

@login_required
def toggle_health_tip_status(request, tip_id):
    if request.user.role != 'staff':
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    health_tip = get_object_or_404(HealthTip, id=tip_id, created_by=request.user)
    health_tip.is_active = not health_tip.is_active
    health_tip.save()
    
    status_text = 'published' if health_tip.is_active else 'unpublished'
    return JsonResponse({
        'success': True,
        'is_active': health_tip.is_active,
        'status_text': status_text,
        'message': f'Health tip has been {status_text}'
    })

# Notification Views
@login_required
def notifications(request):
    notifications = Notification.objects.filter(user=request.user).order_by('-created_at')
    
    # Filter by read/unread status
    status = request.GET.get('status')
    if status == 'unread':
        notifications = notifications.filter(is_read=False)
    elif status == 'read':
        notifications = notifications.filter(is_read=True)
    
    # Filter by type
    notification_type = request.GET.get('type')
    if notification_type:
        notifications = notifications.filter(notification_type=notification_type)
    
    # Mark all as read if requested
    if request.GET.get('mark_all_read') == 'true':
        notifications.filter(is_read=False).update(is_read=True)
        messages.success(request, 'All notifications marked as read.')
        return redirect('management:notifications')
    
    paginator = Paginator(notifications, 15)
    page = request.GET.get('page')
    notifications = paginator.get_page(page)
    
    # Get counts for filters
    total_count = Notification.objects.filter(user=request.user).count()
    unread_count = Notification.objects.filter(user=request.user, is_read=False).count()
    read_count = total_count - unread_count
    
    context = {
        'notifications': notifications,
        'total_count': total_count,
        'unread_count': unread_count,
        'read_count': read_count,
        'current_status': status,
        'current_type': notification_type,
    }
    
    return render(request, 'management/notifications.html', context)

@login_required
def mark_notification_read(request, notification_id):
    notification = get_object_or_404(Notification, id=notification_id, user=request.user)
    notification.is_read = True
    notification.save()
    
    return JsonResponse({'status': 'success'})

@login_required
def mark_all_notifications_read(request):
    """Mark all notifications as read for the current user"""
    if request.method == 'POST':
        updated_count = Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        return JsonResponse({
            'status': 'success', 
            'message': f'{updated_count} notifications marked as read'
        })
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'})

@login_required
def create_system_notification(request):
    """Allow admins to create system-wide notifications"""
    if request.user.role != 'admin':
        messages.error(request, 'Access denied. Only administrators can send system notifications.')
        return redirect('management:dashboard')
    
    if request.method == 'POST':
        title = request.POST.get('title')
        message = request.POST.get('message')
        notification_type = request.POST.get('notification_type', 'general')
        recipient_type = request.POST.get('recipient_type', 'all')
        
        if not title or not message:
            messages.error(request, 'Title and message are required.')
            return render(request, 'management/create_system_notification.html')
        
        # Determine recipients
        if recipient_type == 'students':
            recipients = User.objects.filter(role='student')
        elif recipient_type == 'staff':
            recipients = User.objects.filter(role='staff')
        else:  # all
            recipients = User.objects.filter(role__in=['student', 'staff'])
        
        # Create notifications
        from .utils import create_bulk_notifications
        created_count = len(create_bulk_notifications(recipients, title, message, notification_type))
        
        messages.success(request, f'Successfully sent notification to {created_count} users.')
        return redirect('management:notifications')
    
    return render(request, 'management/create_system_notification.html')

# Feedback Views
@login_required
def feedback_list(request):
    if request.user.role == 'student':
        feedbacks = Feedback.objects.filter(student=request.user)
    else:
        feedbacks = Feedback.objects.all()
    
    paginator = Paginator(feedbacks, 10)
    page = request.GET.get('page')
    feedbacks = paginator.get_page(page)
    
    return render(request, 'management/feedback_list.html', {'feedbacks': feedbacks})

@login_required
def submit_feedback(request, appointment_id=None):
    if request.user.role != 'student':
        messages.error(request, 'Only students can submit feedback')
        return redirect('management:dashboard')
    
    appointment = None
    if appointment_id:
        appointment = get_object_or_404(Appointment, id=appointment_id, student=request.user)
    
    if request.method == 'POST':
        rating = request.POST.get('rating')
        comments = request.POST.get('comments')
        suggestions = request.POST.get('suggestions')
        is_anonymous = request.POST.get('is_anonymous') == 'on'
        
        Feedback.objects.create(
            student=request.user,
            appointment=appointment,
            rating=rating,
            comments=comments,
            suggestions=suggestions,
            is_anonymous=is_anonymous
        )
        
        messages.success(request, 'Feedback submitted successfully!')
        return redirect('management:feedback_list')
    
    return render(request, 'management/submit_feedback.html', {'appointment': appointment})