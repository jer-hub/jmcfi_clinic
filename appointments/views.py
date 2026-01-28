from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.contrib.auth import get_user_model
from django.db.models import Q
import json

from .models import Appointment, AppointmentTypeDefault
from .forms import AppointmentTypeDefaultForm
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
    
    # Apply filters
    status = request.GET.get('status')
    date_from = parse_date(request.GET.get('date_from')) if request.GET.get('date_from') else None
    date_to = parse_date(request.GET.get('date_to')) if request.GET.get('date_to') else None
    
    if status:
        appointments = appointments.filter(status=status)
    if date_from:
        appointments = appointments.filter(date__gte=date_from)
    if date_to:
        appointments = appointments.filter(date__lte=date_to)
    
    appointments = appointments.order_by('-date', '-time')
    appointments = paginate_queryset(appointments, request)
    
    return render(request, 'appointments/appointment_list.html', {'appointments': appointments})


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
            doctors = User.objects.filter(role__in=['staff', 'doctor']).select_related('staff_profile')
            context = _get_appointment_context(doctors)
            return render(request, 'appointments/schedule_appointment.html', context)
        
        try:
            from datetime import datetime
            appointment_date = datetime.strptime(date, '%Y-%m-%d').date()
            appointment_time = datetime.strptime(time, '%H:%M').time()
            
            # Check if date is not in the past
            if appointment_date < timezone.now().date():
                messages.error(request, 'Cannot schedule appointments for past dates.')
                doctors = User.objects.filter(role__in=['staff', 'doctor']).select_related('staff_profile')
                context = _get_appointment_context(doctors)
                return render(request, 'appointments/schedule_appointment.html', context)
            
            # Check if it's a weekend
            if appointment_date.weekday() >= 5:  # Saturday = 5, Sunday = 6
                messages.error(request, 'Appointments are not available on weekends.')
                doctors = User.objects.filter(role__in=['staff', 'doctor']).select_related('staff_profile')
                context = _get_appointment_context(doctors)
                return render(request, 'appointments/schedule_appointment.html', context)
            
            doctor = User.objects.get(id=doctor_id, role__in=['staff', 'doctor'])
            
            # Check for conflicts
            existing_appointment = Appointment.objects.filter(
                doctor=doctor,
                date=appointment_date,
                time=appointment_time,
                status__in=['pending', 'confirmed']
            ).exists()
            
            if existing_appointment:
                messages.error(request, 'This time slot is already booked. Please choose a different time.')
                doctors = User.objects.filter(role__in=['staff', 'doctor']).select_related('staff_profile')
                context = _get_appointment_context(doctors)
                return render(request, 'appointments/schedule_appointment.html', context)
            
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
            
            # Create notification for student
            Notification.objects.create(
                user=request.user,
                title='Appointment Scheduled',
                message=f'Your appointment with Dr. {doctor.get_full_name()} has been scheduled for {appointment_date.strftime("%B %d, %Y")} at {appointment_time.strftime("%I:%M %p")}',
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
    
    doctors = User.objects.filter(role__in=['staff', 'doctor']).select_related('staff_profile')
    context = _get_appointment_context(doctors)
    
    # Add appointment type defaults to context
    appointment_defaults = {}
    for default in AppointmentTypeDefault.objects.filter(is_active=True).select_related('default_doctor'):
        if default.default_doctor:
            appointment_defaults[default.appointment_type] = {
                'doctor_id': default.default_doctor.id,
                'doctor_name': f"Dr. {default.default_doctor.get_full_name()}",
                'department': default.default_doctor.staff_profile.department if hasattr(default.default_doctor, 'staff_profile') else 'N/A'
            }
    context['appointment_defaults'] = appointment_defaults
    
    return render(request, 'appointments/schedule_appointment.html', context)


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


@login_required
def appointment_detail(request, appointment_id):
    appointment = get_object_or_404(Appointment, id=appointment_id)
    
    # Check permissions
    if request.user.role == 'student' and appointment.student != request.user:
        messages.error(request, 'Access denied')
        return redirect('appointments:appointment_list')
    elif request.user.role in ['staff', 'doctor'] and appointment.doctor != request.user and request.user.role != 'admin':
        messages.error(request, 'Access denied')
        return redirect('appointments:appointment_list')
    
    if request.method == 'POST':
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
                    notification_type='appointment'
                )
                
                messages.success(request, 'Appointment cancelled successfully!')
            else:
                messages.error(request, 'Cannot cancel this appointment')
        
        return redirect('appointments:appointment_detail', appointment_id=appointment.id)
    
    return render(request, 'appointments/appointment_detail.html', {'appointment': appointment})


# ============================================================================
# Appointment Settings Views (Admin Only)
# ============================================================================

@login_required
@admin_required
def appointment_type_settings(request):
    """
    View for admin to manage default in-charge doctors for each appointment type.
    Displays all appointment types and their current defaults.
    """
    # Get all appointment type choices
    appointment_types = dict(Appointment.APPOINTMENT_TYPE_CHOICES)
    
    # Get existing defaults
    existing_defaults = AppointmentTypeDefault.objects.select_related('default_doctor').all()
    existing_types = {d.appointment_type: d for d in existing_defaults}
    
    # Create a comprehensive list with all types
    defaults_list = []
    for type_key, type_label in appointment_types.items():
        if type_key in existing_types:
            defaults_list.append(existing_types[type_key])
        else:
            # Create a placeholder for types without defaults
            defaults_list.append({
                'appointment_type': type_key,
                'type_display': type_label,
                'default_doctor': None,
                'is_active': False,
                'is_placeholder': True
            })
    
    context = {
        'defaults_list': defaults_list,
        'appointment_types': appointment_types,
    }
    
    return render(request, 'appointments/appointment_settings/appointment_type_settings.html', context)


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
            
            type_display = default.get_appointment_type_display()
            doctor_name = f"Dr. {default.default_doctor.get_full_name()}" if default.default_doctor else "None"
            
            messages.success(
                request,
                f'Successfully updated default in-charge for {type_display} to {doctor_name}.'
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
