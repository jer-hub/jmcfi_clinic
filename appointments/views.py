from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.contrib.auth import get_user_model
from django.db.models import Q, Case, When, Value, IntegerField
import json

from .models import Appointment, AppointmentTypeDefault
from .forms import AppointmentTypeDefaultForm
from .appointment_utils import check_appointment_availability, get_available_time_slots, format_conflict_message
from core.models import Notification
from core.decorators import role_required, admin_required

User = get_user_model()


def paginate_queryset(queryset, request, per_page=10):
    """Helper function for pagination"""
    from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
    
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
def appointment_list(request):
    """Display list of appointments based on user role"""
    # Get appointments based on user role
    if request.user.role == 'student':
        appointments = Appointment.objects.filter(student=request.user)
    elif request.user.role in ['staff', 'doctor']:
        appointments = Appointment.objects.filter(doctor=request.user)
    elif request.user.role == 'admin':
        appointments = Appointment.objects.all()
    else:
        appointments = Appointment.objects.none()

    # Get filter parameters
    status = request.GET.get('status')
    date_from_str = request.GET.get('date_from')
    date_to_str = request.GET.get('date_to')
    doctor_id = request.GET.get('doctor')
    appointment_type = request.GET.get('appointment_type')

    # Apply filters
    if status:
        appointments = appointments.filter(status=status)
    if date_from_str:
        date_from = parse_date(date_from_str)
        if date_from:
            appointments = appointments.filter(date__gte=date_from)
    if date_to_str:
        date_to = parse_date(date_to_str)
        if date_to:
            appointments = appointments.filter(date__lte=date_to)
    if doctor_id:
        appointments = appointments.filter(doctor_id=doctor_id)
    if appointment_type:
        appointments = appointments.filter(appointment_type=appointment_type)

    # Status totals for the currently filtered result set
    status_totals = {
        'pending': appointments.filter(status='pending').count(),
        'confirmed': appointments.filter(status='confirmed').count(),
        'completed': appointments.filter(status='completed').count(),
        'cancelled': appointments.filter(status='cancelled').count(),
    }

    # Order by latest date and time first
    appointments = appointments.select_related('student', 'doctor').prefetch_related('dental_records', 'medicalrecord_set').order_by('-date', '-time')
    
    paginated_appointments = paginate_queryset(appointments, request)

    # Get data for filter dropdowns
    doctors = User.objects.filter(role='doctor').order_by('first_name', 'last_name')
    appointment_types = Appointment.APPOINTMENT_TYPE_CHOICES

    context = {
        'appointments': paginated_appointments,
        'status_totals': status_totals,
        'doctors': doctors,
        'appointment_types': appointment_types,
        'current_filters': {
            'status': status,
            'date_from': date_from_str,
            'date_to': date_to_str,
            'doctor': int(doctor_id) if doctor_id else None,
            'appointment_type': appointment_type,
        }
    }
    
    return render(request, 'appointments/appointment_list.html', context)


@login_required
def schedule_appointment(request):
    if request.user.role != 'student':
        messages.error(request, 'Only students can schedule appointments')
        return redirect('core:dashboard')
    
    if request.method == 'POST':
        doctor_id = request.POST.get('doctor')
        appointment_type = request.POST.get('appointment_type')
        date = request.POST.get('date')
        time = request.POST.get('time')
        reason = request.POST.get('reason')
        
        # Validation
        if not all([doctor_id, appointment_type, date, time, reason]):
            messages.error(request, 'All fields are required.')
            return render(request, 'appointments/schedule_appointment.html', _get_schedule_context())
        
        try:
            from datetime import datetime
            appointment_date = datetime.strptime(date, '%Y-%m-%d').date()
            appointment_time = datetime.strptime(time, '%H:%M').time()
            
            # Check if date is not in the past
            if appointment_date < timezone.now().date():
                messages.error(request, 'Cannot schedule appointments for past dates.')
                return render(request, 'appointments/schedule_appointment.html', _get_schedule_context())
            
            # Check if it's a weekend
            if appointment_date.weekday() >= 5:  # Saturday = 5, Sunday = 6
                messages.error(request, 'Appointments are not available on weekends.')
                return render(request, 'appointments/schedule_appointment.html', _get_schedule_context())
            
            doctor = User.objects.get(id=doctor_id, role='doctor', is_active=True)
            
            # Validate that the selected doctor is allowed for this appointment type
            type_default = AppointmentTypeDefault.objects.filter(
                appointment_type=appointment_type, is_active=True
            ).prefetch_related('assigned_doctors').first()
            if type_default and type_default.assigned_doctors.exists():
                allowed_ids = list(type_default.assigned_doctors.values_list('id', flat=True))
                if doctor.id not in allowed_ids:
                    messages.error(request, 'The selected doctor is not available for this appointment type.')
                    return render(request, 'appointments/schedule_appointment.html', _get_schedule_context())

            # Check for conflicts using interval-based validation (30 min buffer)
            is_available, conflicts = check_appointment_availability(doctor, appointment_date, appointment_time)
            
            if not is_available:
                conflict_msg = format_conflict_message(doctor, conflicts)
                messages.error(request, conflict_msg)
                return render(request, 'appointments/schedule_appointment.html', _get_schedule_context())
            
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
                notification_type='appointment',
                transaction_type='appointment_scheduled',
                related_id=appointment.id
            )
            
            messages.success(request, 'Appointment scheduled successfully!')
            return redirect('appointments:appointment_list')
            
        except User.DoesNotExist:
            messages.error(request, 'Invalid doctor selected')
        except ValueError:
            messages.error(request, 'Invalid date or time format')
        except Exception as e:
            messages.error(request, 'An error occurred while scheduling the appointment. Please try again.')
    
    return render(request, 'appointments/schedule_appointment.html', _get_schedule_context())


def _get_appointment_context(doctors):
    """Helper function to prepare context for appointment scheduling"""
    # Define mapping between appointment types and specializations/departments
    appointment_type_mapping = {
        'consultation': ['General Medicine', 'Internal Medicine', 'Family Medicine'],
        'checkup': ['General Medicine', 'Internal Medicine', 'Family Medicine'],
        'vaccination': ['Immunology', 'Pediatrics', 'General Medicine'],
        'emergency': ['Emergency Medicine', 'General Medicine'],
        'followup': ['General Medicine', 'Internal Medicine', 'Family Medicine'],
        'dental': ['Dent', 'Dental', 'Dentistry', 'Dental Medicine', 'Oral Medicine', 'Dental Clinic']
    }
    
    # Create a dictionary to store default doctor IDs for each appointment type
    default_doctors = {}
    
    for apt_type, specializations in appointment_type_mapping.items():
        # Try to find a doctor with matching specialization
        for specialization in specializations:
            matching_doctor = doctors.filter(
                staff_profile__specialization__icontains=specialization
            ).first()
            if matching_doctor:
                default_doctors[apt_type] = matching_doctor.id
                break
        
        # If no match found by specialization, try department
        if apt_type not in default_doctors:
            for specialization in specializations:
                matching_doctor = doctors.filter(
                    staff_profile__department__icontains=specialization
                ).first()
                if matching_doctor:
                    default_doctors[apt_type] = matching_doctor.id
                    break
        
        # If still no match, use the first available doctor
        if apt_type not in default_doctors and doctors.exists():
            default_doctors[apt_type] = doctors.first().id
    
    # Prepare doctors data with their specializations for JavaScript
    doctors_data = []
    for doctor in doctors:
        doctors_data.append({
            'id': doctor.id,
            'name': doctor.get_full_name(),
            'specialization': doctor.staff_profile.specialization if hasattr(doctor, 'staff_profile') and doctor.staff_profile.specialization else '',
            'department': doctor.staff_profile.department if hasattr(doctor, 'staff_profile') and doctor.staff_profile.department else ''
        })
    
    return {
        'doctors': doctors,
        'default_doctors': json.dumps(default_doctors),
        'doctors_data': doctors_data
    }


def _get_schedule_context():
    """
    Build the full context for the schedule-appointment page.
    Only includes active AppointmentTypeDefault records,
    and only the doctors assigned to those types (or all active
    doctors when a type has no restriction).
    """
    active_defaults = (
        AppointmentTypeDefault.objects
        .filter(is_active=True)
        .prefetch_related('assigned_doctors')
        .order_by('appointment_type')
    )

    type_doctor_map = {}  # { appointment_type: [doctor_id, ...] }
    all_assigned_ids = set()
    has_unrestricted_type = False

    for default in active_defaults:
        assigned = list(
            default.assigned_doctors.filter(role='doctor', is_active=True).values_list('id', flat=True)
        )
        type_doctor_map[default.appointment_type] = assigned
        if assigned:
            all_assigned_ids.update(assigned)
        else:
            has_unrestricted_type = True  # this type allows all doctors

    # If any type is unrestricted (no assigned doctors), show all active doctors.
    # Otherwise show only those who appear in at least one type.
    if has_unrestricted_type or not active_defaults.exists():
        doctors = User.objects.filter(
            role='doctor', is_active=True
        ).select_related('staff_profile').order_by('first_name', 'last_name')
    else:
        doctors = User.objects.filter(
            id__in=all_assigned_ids, role='doctor', is_active=True
        ).select_related('staff_profile').order_by('first_name', 'last_name')

    return {
        'doctors': doctors,
        'active_defaults': active_defaults,
        'type_doctor_map': json.dumps(type_doctor_map),
    }


@login_required
def appointment_detail(request, appointment_id):
    appointment = get_object_or_404(
        Appointment.objects.select_related('student', 'doctor').prefetch_related('dental_records', 'medicalrecord_set'),
        id=appointment_id,
    )
    
    # Check permissions
    if request.user.role == 'student' and appointment.student != request.user:
        messages.error(request, 'Access denied')
        return redirect('appointments:appointment_list')
    elif request.user.role in ['staff', 'doctor'] and appointment.doctor != request.user and request.user.role != 'admin':
        messages.error(request, 'Access denied')
        return redirect('appointments:appointment_list')
    
    if request.method == 'POST':
        next_url = request.POST.get('next')

        if request.user.role in ['staff', 'doctor', 'admin']:
            status = request.POST.get('status')
            notes = request.POST.get('notes')
            
            if status:
                appointment.status = status
            if notes is not None:  # Allow empty notes
                appointment.notes = notes
            appointment.save()
            
            # Create notification for student
            # Map status to transaction_type
            status_to_transaction = {
                'pending': 'appointment_reminder',
                'confirmed': 'appointment_confirmed',
                'completed': 'appointment_completed',
                'cancelled': 'appointment_cancelled',
            }
            Notification.objects.create(
                user=appointment.student,
                title='Appointment Update',
                message=f'Your appointment status has been updated to {appointment.get_status_display()}',
                notification_type='appointment',
                transaction_type=status_to_transaction.get(appointment.status, 'appointment_reminder'),
                related_id=appointment.id
            )
            
            messages.success(request, 'Appointment updated successfully!')
            
        elif request.user.role == 'student' and appointment.student == request.user:
            # Allow students to cancel their own appointments
            status = request.POST.get('status')
            if status == 'cancelled' and appointment.status in ['pending']:
                appointment.status = 'cancelled'
                appointment.save()
                
                # Create notification for doctor
                Notification.objects.create(
                    user=appointment.doctor,
                    title='Appointment Cancelled',
                    message=f'Appointment with {request.user.get_full_name()} has been cancelled',
                    notification_type='appointment',
                    transaction_type='appointment_cancelled',
                    related_id=appointment.id
                )
                
                messages.success(request, 'Appointment cancelled successfully!')
            else:
                messages.error(request, 'Cannot cancel this appointment')
        
        if next_url and next_url.startswith('/'):
            return redirect(next_url)

        return redirect('appointments:appointment_detail', appointment_id=appointment.id)
    
    return render(request, 'appointments/appointment_detail.html', {'appointment': appointment})


# ============================================================================
# Appointment Settings Views (Admin Only)
# ============================================================================

@login_required
@admin_required
def appointment_type_settings(request):
    """
    View for admin to assign doctors to each appointment type via inline forms.
    """
    appointment_types = dict(Appointment.APPOINTMENT_TYPE_CHOICES)
    existing_defaults = {
        d.appointment_type: d
        for d in AppointmentTypeDefault.objects.prefetch_related('assigned_doctors').all()
    }

    settings_data = []
    for type_key, type_label in appointment_types.items():
        instance = existing_defaults.get(type_key)
        initial = {'appointment_type': type_key, 'is_active': True} if not instance else {}
        form = AppointmentTypeDefaultForm(instance=instance, initial=initial, auto_id=f'id_{type_key}_%s')
        settings_data.append({
            'type_key': type_key,
            'type_label': type_label,
            'form': form,
            'instance': instance,
        })

    return render(request, 'appointments/appointment_settings/appointment_type_settings.html', {
        'settings_data': settings_data,
    })


@login_required
@admin_required
def edit_appointment_type_default(request, type_key=None):
    """
    View for admin to edit or create a default in-charge for an appointment type.
    """
    # Try to get existing default or create new
    if type_key:
        appointment_default = AppointmentTypeDefault.objects.filter(appointment_type=type_key).first()
    else:
        appointment_default = None
    
    if request.method == 'POST':
        form = AppointmentTypeDefaultForm(request.POST, instance=appointment_default)
        if form.is_valid():
            default = form.save(commit=False)
            default.updated_by = request.user
            default.save()
            form.save_m2m()  # persist assigned_doctors M2M after commit=False save
            
            type_display = default.get_appointment_type_display()
            messages.success(
                request,
                f'Successfully updated doctor assignments for {type_display}.'
            )
            return redirect('appointments:appointment_type_settings')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        # Pre-fill appointment type if creating new
        initial_data = {}
        if type_key and not appointment_default:
            initial_data['appointment_type'] = type_key
            initial_data['is_active'] = True
        
        form = AppointmentTypeDefaultForm(instance=appointment_default, initial=initial_data)
    
    context = {
        'form': form,
        'appointment_default': appointment_default,
        'type_key': type_key,
        'is_edit': appointment_default is not None,
    }
    
    return render(request, 'appointments/appointment_settings/edit_appointment_type_default.html', context)


@login_required
@admin_required
def toggle_appointment_type_default(request, default_id):
    """
    Quick toggle for activating/deactivating an appointment type default.
    """
    if request.method == 'POST':
        default = get_object_or_404(AppointmentTypeDefault, id=default_id)
        default.is_active = not default.is_active
        default.updated_by = request.user
        default.save()
        
        status = "activated" if default.is_active else "deactivated"
        messages.success(
            request,
            f'Default for {default.get_appointment_type_display()} has been {status}.'
        )
    
    return redirect('appointments:appointment_type_settings')


@login_required
@admin_required
def delete_appointment_type_default(request, default_id):
    """
    Delete an appointment type default.
    """
    if request.method == 'POST':
        default = get_object_or_404(AppointmentTypeDefault, id=default_id)
        type_display = default.get_appointment_type_display()
        default.delete()
        
        messages.success(
            request,
            f'Default in-charge for {type_display} has been removed.'
        )
    
    return redirect('appointments:appointment_type_settings')


@login_required
@role_required('doctor', 'admin')
def schedule_for_student(request):
    """
    Allows doctors or admins to schedule an appointment for a student.
    """
    if request.method == 'POST':
        student_id = request.POST.get('student')
        appointment_type = request.POST.get('appointment_type')
        date_str = request.POST.get('date')
        time_str = request.POST.get('time')
        reason = request.POST.get('reason')

        # --- Validation ---
        if not all([student_id, appointment_type, date_str, time_str, reason]):
            messages.error(request, 'All fields are required.')
            return redirect('appointments:schedule_for_student')

        try:
            student = User.objects.get(id=student_id, role='student')
            doctor = request.user
            from datetime import datetime
            appointment_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            appointment_time = datetime.strptime(time_str, '%H:%M').time()

            # 1. Check if date is in the past
            if appointment_date < timezone.now().date():
                messages.error(request, 'Cannot schedule appointments for past dates.')
                return redirect('appointments:schedule_for_student')

            # 2. Check for student conflict
            student_conflict = Appointment.objects.filter(
                student=student,
                date=appointment_date,
                time=appointment_time,
                status__in=['pending', 'confirmed']
            ).exists()
            if student_conflict:
                messages.error(request, f'{student.get_full_name()} already has a pending or confirmed appointment at this time.')
                return redirect('appointments:schedule_for_student')

            # 3. Check for doctor conflict
            doctor_conflict = Appointment.objects.filter(
                doctor=doctor,
                date=appointment_date,
                time=appointment_time,
                status__in=['pending', 'confirmed']
            ).exists()
            if doctor_conflict:
                messages.error(request, 'You already have an appointment scheduled at this time.')
                return redirect('appointments:schedule_for_student')

            # --- Create Appointment ---
            appointment = Appointment.objects.create(
                student=student,
                doctor=doctor,
                appointment_type=appointment_type,
                date=appointment_date,
                time=appointment_time,
                reason=reason,
                status='confirmed'  # Automatically confirmed
            )

            # --- Create Notification for Student ---
            Notification.objects.create(
                user=student,
                title='Appointment Scheduled for You',
                message=f'Dr. {doctor.get_full_name()} has scheduled a new appointment for you on {appointment_date.strftime("%B %d, %Y")} at {appointment_time.strftime("%I:%M %p")}.',
                notification_type='appointment',
                transaction_type='appointment_confirmed',
                related_id=appointment.id
            )

            messages.success(request, f'Appointment successfully scheduled for {student.get_full_name()}.')
            return redirect('appointments:appointment_list')

        except User.DoesNotExist:
            messages.error(request, 'Invalid student selected.')
        except ValueError:
            messages.error(request, 'Invalid date or time format.')
        except Exception as e:
            messages.error(request, f'An error occurred: {e}')
        
        return redirect('appointments:schedule_for_student')

    context = {
        'appointment_types': Appointment.APPOINTMENT_TYPE_CHOICES
    }
    return render(request, 'appointments/schedule_for_student.html', context)
