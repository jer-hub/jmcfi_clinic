from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
from django.contrib import messages
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.db.models import Q
from django.utils import timezone
from django.contrib.auth import get_user_model

from .models import Notification, StudentProfile, StaffProfile
from .forms import StudentProfileForm, StaffProfileForm, UserCreationForm, UserEditForm, PasswordResetForm
from .utils import (
    get_user_profile, create_notification, paginate_queryset,
    create_bulk_notifications
)
from .decorators import admin_required

User = get_user_model()


# =====================
# Authentication Views
# =====================

@login_required
def logout_view(request):
    """Handle user logout"""
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('account_login')


@login_required
def profile_required(request):
    """View to show profile completion required page – access to all services is blocked."""
    from .utils import get_missing_profile_fields
    # Returns a list of (field_name, friendly_label) tuples
    missing = get_missing_profile_fields(request.user)
    # Pass only the labels to the template
    missing_labels = [label for _field, label in missing]
    return render(request, 'core/profile_required.html', {
        'missing_fields': missing_labels,
    })


# =====================
# Dashboard Views
# =====================

@login_required
def dashboard(request):
    """Main dashboard view - role-based content"""
    from appointments.models import Appointment
    from medical_records.models import MedicalRecord
    from document_request.models import DocumentRequest as CertificateRequest
    from health_tips.models import HealthTip
    from feedback.models import Feedback
    
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
    
    elif request.user.role in ['staff', 'doctor']:
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
            'total_staff': User.objects.filter(role__in=['staff', 'doctor']).count(),
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
    
    return render(request, 'core/dashboard.html', context)


# =====================
# Notification Views
# =====================

@login_required
def notifications(request):
    """Display user notifications"""
    notifications_qs = Notification.objects.filter(user=request.user).order_by('-created_at')
    
    # Filter by read/unread status
    status = request.GET.get('status')
    if status == 'unread':
        notifications_qs = notifications_qs.filter(is_read=False)
    elif status == 'read':
        notifications_qs = notifications_qs.filter(is_read=True)
    
    # Filter by type
    notification_type = request.GET.get('type')
    if notification_type:
        notifications_qs = notifications_qs.filter(notification_type=notification_type)
    
    # Mark all as read if requested
    if request.GET.get('mark_all_read') == 'true':
        notifications_qs.filter(is_read=False).update(is_read=True)
        messages.success(request, 'All notifications marked as read.')
        return redirect('core:notifications')
    
    paginator = Paginator(notifications_qs, 15)
    page = request.GET.get('page')
    notifications_page = paginator.get_page(page)
    
    # Get counts for filters
    total_count = Notification.objects.filter(user=request.user).count()
    unread_count = Notification.objects.filter(user=request.user, is_read=False).count()
    read_count = total_count - unread_count
    
    context = {
        'notifications': notifications_page,
        'total_count': total_count,
        'unread_count': unread_count,
        'read_count': read_count,
        'current_status': status,
        'current_type': notification_type,
    }
    
    return render(request, 'core/notifications.html', context)


@login_required
def mark_notification_read(request, notification_id):
    """Mark single notification as read"""
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
def clear_all_notifications(request):
    """Delete all notifications for the current user"""
    if request.method == 'POST':
        deleted_count = Notification.objects.filter(user=request.user).count()
        Notification.objects.filter(user=request.user).delete()
        return JsonResponse({
            'status': 'success', 
            'message': f'{deleted_count} notifications cleared',
            'count': deleted_count
        })
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'})


@login_required
def create_system_notification(request):
    """Allow admins to create system-wide notifications"""
    if request.user.role != 'admin':
        messages.error(request, 'Access denied. Only administrators can send system notifications.')
        return redirect('core:dashboard')
    
    if request.method == 'POST':
        title = request.POST.get('title')
        message = request.POST.get('message')
        notification_type = request.POST.get('notification_type', 'general')
        recipient_type = request.POST.get('recipient_type', 'all')
        
        if not title or not message:
            messages.error(request, 'Title and message are required.')
            return render(request, 'core/create_system_notification.html')
        
        # Determine recipients
        if recipient_type == 'students':
            recipients = User.objects.filter(role='student')
        elif recipient_type == 'staff_only':
            recipients = User.objects.filter(role='staff')
        elif recipient_type == 'doctors':
            recipients = User.objects.filter(role='doctor')
        elif recipient_type == 'admins':
            recipients = User.objects.filter(role='admin')
        elif recipient_type == 'staff_and_doctors':
            recipients = User.objects.filter(role__in=['staff', 'doctor'])
        elif recipient_type == 'non_students':
            recipients = User.objects.filter(role__in=['staff', 'doctor', 'admin'])
        else:  # all
            recipients = User.objects.filter(role__in=['student', 'staff', 'doctor', 'admin'])
        
        # Create notifications
        created_count = len(create_bulk_notifications(recipients, title, message, notification_type))
        
        messages.success(request, 'Notification sent successfully.')
        return redirect('core:notifications')
    
    return render(request, 'core/create_system_notification.html')


# =====================
# Profile Views
# =====================

@login_required
def profile_view(request):
    """Display user profile information with related dental and medical records"""
    from dental_records.models import DentalRecord
    
    profile = get_user_profile(request.user)
    
    # Get the latest dental record for the user
    dental_record = None
    try:
        dental_record = DentalRecord.objects.filter(patient=request.user).select_related(
            'vital_signs', 'health_questionnaire', 'systems_review'
        ).latest('created_at')
    except DentalRecord.DoesNotExist:
        pass
    
    # Calculate profile completion percentage
    completion_percentage = 0
    if profile:
        if request.user.role == 'student':
            required_fields = [
                'student_id', 'date_of_birth', 'phone', 
                'emergency_contact', 'emergency_phone', 'blood_type',
                'gender', 'civil_status', 'address'
            ]
        else:
            required_fields = [
                'staff_id', 'department', 'phone',
                'date_of_birth', 'gender'
            ]
        
        filled_count = 0
        for field in required_fields:
            value = getattr(profile, field, None)
            if value and (not isinstance(value, str) or value.strip()):
                filled_count += 1
        completion_percentage = int((filled_count / len(required_fields)) * 100)
    
    context = {
        'user': request.user,
        'profile': profile,
        'dental_record': dental_record,
        'completion_percentage': completion_percentage,
    }
    
    return render(request, 'core/profile.html', context)


@login_required
def quick_edit_profile(request):
    """Quick edit a single profile field via AJAX/form submission"""
    if request.method != 'POST':
        messages.error(request, 'Invalid request method.')
        return redirect('core:profile')
    
    profile = get_user_profile(request.user)
    if not profile:
        messages.error(request, 'Profile not found. Please complete your profile first.')
        return redirect('core:edit_profile')
    
    field_name = request.POST.get('field_name')
    field_value = request.POST.get('field_value', '').strip()
    
    # Define allowed fields for quick edit (security measure)
    allowed_fields = [
        'phone', 'telephone_number', 'emergency_contact', 'emergency_phone',
        'address', 'allergies', 'medical_conditions', 'middle_name',
        'place_of_birth', 'course', 'year_level', 'department', 'position',
        'specialization'
    ]
    
    # Fields that need special handling
    date_fields = ['date_of_birth']
    select_fields = ['gender', 'civil_status', 'blood_type']
    
    all_allowed = allowed_fields + date_fields + select_fields
    
    if field_name not in all_allowed:
        messages.error(request, 'This field cannot be edited via quick edit.')
        return redirect('core:profile')
    
    # Validate the field exists on the profile model
    if not hasattr(profile, field_name):
        messages.error(request, 'Invalid field.')
        return redirect('core:profile')
    
    try:
        # Handle date fields
        if field_name in date_fields:
            if field_value:
                from datetime import datetime
                field_value = datetime.strptime(field_value, '%Y-%m-%d').date()
            else:
                field_value = None
        
        # Set the value
        setattr(profile, field_name, field_value)
        profile.save()
        
        # Clear profile completion cache
        session_key = f'profile_complete_{request.user.id}'
        if session_key in request.session:
            del request.session[session_key]
        
        messages.success(request, f'Successfully updated your {field_name.replace("_", " ").title()}.')
    except Exception as e:
        messages.error(request, f'Error updating field: {str(e)}')
    
    return redirect('core:profile')


@login_required
def edit_profile(request):
    """Edit user profile information"""
    from dental_records.models import DentalRecord
    
    profile = get_user_profile(request.user)
    is_first_time = profile is None
    
    if request.user.role == 'student':
        form_class = StudentProfileForm
    elif request.user.role in ['staff', 'doctor']:
        form_class = StaffProfileForm
    else:
        messages.error(request, 'Profile editing not available for your role.')
        return redirect('core:dashboard')
    
    # Check for dental record to auto-fill data
    dental_record = None
    try:
        dental_record = DentalRecord.objects.filter(patient=request.user).latest('created_at')
    except DentalRecord.DoesNotExist:
        pass
    
    if request.method == 'POST':
        # Handle auto-fill request
        if 'autofill_from_dental' in request.POST and dental_record:
            # Create initial data from dental record
            initial_data = {}
            
            if dental_record.middle_name:
                initial_data['middle_name'] = dental_record.middle_name
            if dental_record.gender:
                initial_data['gender'] = dental_record.gender
            if dental_record.civil_status:
                initial_data['civil_status'] = dental_record.civil_status
            if dental_record.date_of_birth:
                initial_data['date_of_birth'] = dental_record.date_of_birth
            if dental_record.place_of_birth:
                initial_data['place_of_birth'] = dental_record.place_of_birth
            if dental_record.age:
                initial_data['age'] = dental_record.age
            if dental_record.address:
                initial_data['address'] = dental_record.address
            if dental_record.contact_number:
                initial_data['phone'] = dental_record.contact_number
            if dental_record.telephone_number:
                initial_data['telephone_number'] = dental_record.telephone_number
            if dental_record.guardian_name:
                initial_data['emergency_contact'] = dental_record.guardian_name
            if dental_record.guardian_contact:
                initial_data['emergency_phone'] = dental_record.guardian_contact
            if dental_record.department_college_office:
                if request.user.role == 'student':
                    # Try to parse as course
                    initial_data['course'] = dental_record.department_college_office
                else:
                    initial_data['department'] = dental_record.department_college_office
            
            # Merge with existing profile data if available
            if profile:
                form = form_class(initial=initial_data, instance=profile)
                # Update form with autofilled values
                for key, value in initial_data.items():
                    if key in form.fields:
                        form.initial[key] = value
            else:
                form = form_class(initial=initial_data)
            
            messages.success(request, 'Profile auto-filled from your dental record. Please review and save.')
            
        else:
            # Normal form submission
            form = form_class(request.POST, request.FILES, instance=profile)
            if form.is_valid():
                profile = form.save(commit=False)
                if not profile.user_id:
                    profile.user = request.user
                profile.save()
                
                # Clear profile completion cache
                session_key = f'profile_complete_{request.user.id}'
                if session_key in request.session:
                    del request.session[session_key]
                
                if is_first_time:
                    messages.success(request, 'Welcome! Your profile has been created successfully!')
                    # Clear the welcome shown flag
                    request.session.pop('profile_welcome_shown', None)
                else:
                    messages.success(request, 'Profile updated successfully!')
                
                # Redirect to dashboard after profile completion
                return redirect('core:dashboard')
            else:
                if is_first_time:
                    messages.error(request, 'Please complete all required fields to set up your profile.')
                else:
                    messages.error(request, 'Please correct the errors below.')
    else:
        form = form_class(instance=profile)
        
        # Only show welcome message for first-time users, and only once per session
        if is_first_time and not request.session.get('profile_welcome_shown'):
            messages.info(request, 
                f'Welcome to JMCFI Clinic! Please complete your profile to get started.')
            request.session['profile_welcome_shown'] = True
    
    context = {
        'form': form,
        'profile': profile,
        'user': request.user,
        'is_first_time': is_first_time,
        'dental_record': dental_record,
    }
    
    return render(request, 'core/edit_profile.html', context)


# =====================
# User Management Views (Admin Only)
# =====================

@login_required
@admin_required
def user_management(request):
    """List all users with filtering and search"""
    from appointments.models import Appointment
    from medical_records.models import MedicalRecord
    from document_request.models import DocumentRequest as CertificateRequest
    
    # Get filter parameters
    role_filter = request.GET.get('role', '')
    status_filter = request.GET.get('status', '')
    search_query = request.GET.get('search', '')
    
    # Base queryset
    users = User.objects.all().order_by('-date_joined')
    
    # Apply filters
    if role_filter:
        users = users.filter(role=role_filter)
    
    if status_filter == 'active':
        users = users.filter(is_active=True)
    elif status_filter == 'inactive':
        users = users.filter(is_active=False)
    
    # Apply search
    if search_query:
        users = users.filter(
            Q(username__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query)
        )
    
    # Get statistics
    stats = {
        'total_users': User.objects.count(),
        'total_students': User.objects.filter(role='student').count(),
        'total_staff': User.objects.filter(role__in=['staff', 'doctor']).count(),
        'total_admins': User.objects.filter(role='admin').count(),
        'active_users': User.objects.filter(is_active=True).count(),
        'inactive_users': User.objects.filter(is_active=False).count(),
    }
    
    # Paginate results
    users = paginate_queryset(users, request, per_page=20)
    
    context = {
        'users': users,
        'stats': stats,
        'role_filter': role_filter,
        'status_filter': status_filter,
        'search_query': search_query,
    }
    
    return render(request, 'core/user_management/user_list.html', context)


@login_required
@admin_required
def user_detail(request, user_id):
    """View detailed information about a specific user"""
    from appointments.models import Appointment
    from medical_records.models import MedicalRecord
    from document_request.models import DocumentRequest as CertificateRequest
    
    user = get_object_or_404(User, id=user_id)
    profile = get_user_profile(user)
    
    # Get user statistics
    if user.role == 'student':
        stats = {
            'Total Appointments': Appointment.objects.filter(student=user).count(),
            'Completed Appointments': Appointment.objects.filter(student=user, status='completed').count(),
            'Pending Appointments': Appointment.objects.filter(student=user, status='pending').count(),
            'Medical Records': MedicalRecord.objects.filter(student=user).count(),
            'Certificate Requests': CertificateRequest.objects.filter(student=user).count(),
        }
        recent_activity = {
            'appointments': Appointment.objects.filter(student=user).order_by('-created_at')[:5],
            'medical_records': MedicalRecord.objects.filter(student=user).order_by('-created_at')[:5],
        }
    elif user.role == 'staff':
        stats = {
            'Total Appointments': Appointment.objects.filter(doctor=user).count(),
            'Completed Appointments': Appointment.objects.filter(doctor=user, status='completed').count(),
            'Pending Appointments': Appointment.objects.filter(doctor=user, status='pending').count(),
            'Medical Records': MedicalRecord.objects.filter(doctor=user).count(),
            'Certificates Processed': CertificateRequest.objects.filter(processed_by=user).count(),
        }
        recent_activity = {
            'appointments': Appointment.objects.filter(doctor=user).order_by('-created_at')[:5],
            'medical_records': MedicalRecord.objects.filter(doctor=user).order_by('-created_at')[:5],
        }
    else:
        stats = {}
        recent_activity = {}
    
    context = {
        'viewed_user': user,
        'profile': profile,
        'stats': stats,
        'recent_activity': recent_activity,
    }
    
    return render(request, 'core/user_management/user_detail.html', context)


@login_required
@admin_required
def user_create(request):
    """Create a new user"""
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            
            # Create notification for the new user
            create_notification(
                user=user,
                title='Welcome to JMCFI Clinic',
                message=f'Your account has been created. Please complete your profile to get started.',
                notification_type='general'
            )
            
            messages.success(request, f'User "{user.username}" created successfully!')
            return redirect('core:user_detail', user_id=user.id)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = UserCreationForm()
    
    context = {
        'form': form,
        'action': 'Create',
    }
    
    return render(request, 'core/user_management/user_form.html', context)


@login_required
@admin_required
def user_edit(request, user_id):
    """Edit an existing user"""
    user = get_object_or_404(User, id=user_id)
    
    # Prevent editing admin users
    if user.role == 'admin':
        messages.error(request, 'Cannot edit admin users.')
        return redirect('core:user_detail', user_id=user.id)
    
    if request.method == 'POST':
        form = UserEditForm(request.POST, instance=user)
        if form.is_valid():
            old_role = user.role
            user = form.save()
            
            # If role changed, handle profile migration
            if old_role != user.role:
                if old_role == 'student' and user.role == 'staff':
                    # Delete student profile and create staff profile
                    try:
                        user.student_profile.delete()
                    except:
                        pass
                    if not hasattr(user, 'staff_profile'):
                        StaffProfile.objects.create(
                            user=user,
                            staff_id=f'TEMP_{user.id}',
                            phone='',
                            department='Pending'
                        )
                elif old_role == 'staff' and user.role == 'student':
                    # Delete staff profile and create student profile
                    try:
                        user.staff_profile.delete()
                    except:
                        pass
                    if not hasattr(user, 'student_profile'):
                        StudentProfile.objects.create(
                            user=user,
                            student_id=f'TEMP_{user.id}',
                            phone='',
                            emergency_contact='',
                            emergency_phone='',
                            date_of_birth='2000-01-01'
                        )
                
                messages.info(request, f'User role changed from {old_role} to {user.role}. Please update their profile.')
            
            messages.success(request, f'User "{user.username}" updated successfully!')
            return redirect('core:user_detail', user_id=user.id)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = UserEditForm(instance=user)
    
    context = {
        'form': form,
        'action': 'Edit',
        'viewed_user': user,
    }
    
    return render(request, 'core/user_management/user_form.html', context)


@login_required
@admin_required
def user_delete(request, user_id):
    """Delete a user"""
    user = get_object_or_404(User, id=user_id)
    
    # Prevent deleting admin users
    if user.role == 'admin':
        messages.error(request, 'Cannot delete admin users.')
        return redirect('core:user_detail', user_id=user.id)
    
    # Prevent deleting self
    if user.id == request.user.id:
        messages.error(request, 'Cannot delete your own account.')
        return redirect('core:user_detail', user_id=user.id)
    
    if request.method == 'POST':
        username = user.username
        user.delete()
        messages.success(request, f'User "{username}" has been deleted.')
        return redirect('core:user_management')
    
    context = {
        'viewed_user': user,
    }
    
    return render(request, 'core/user_management/user_delete_confirm.html', context)


@login_required
@admin_required
def user_toggle_status(request, user_id):
    """Toggle user active/inactive status"""
    user = get_object_or_404(User, id=user_id)
    
    # Prevent deactivating admin users
    if user.role == 'admin':
        messages.error(request, 'Cannot deactivate admin users.')
        return redirect('core:user_detail', user_id=user.id)
    
    # Prevent deactivating self
    if user.id == request.user.id:
        messages.error(request, 'Cannot deactivate your own account.')
        return redirect('core:user_detail', user_id=user.id)
    
    user.is_active = not user.is_active
    user.save()
    
    status = 'activated' if user.is_active else 'deactivated'
    messages.success(request, f'User "{user.username}" has been {status}.')
    
    # Create notification for the user
    if user.is_active:
        create_notification(
            user=user,
            title='Account Activated',
            message='Your account has been activated by an administrator.',
            notification_type='general'
        )
    else:
        create_notification(
            user=user,
            title='Account Deactivated',
            message='Your account has been deactivated. Please contact an administrator for more information.',
            notification_type='general'
        )
    
    return redirect('core:user_detail', user_id=user.id)


@login_required
@admin_required
def user_reset_password(request, user_id):
    """Reset user password"""
    user = get_object_or_404(User, id=user_id)
    
    # Prevent resetting admin passwords
    if user.role == 'admin':
        messages.error(request, 'Cannot reset admin user passwords.')
        return redirect('core:user_detail', user_id=user.id)
    
    if request.method == 'POST':
        form = PasswordResetForm(request.POST)
        if form.is_valid():
            new_password = form.cleaned_data['new_password1']
            user.set_password(new_password)
            user.save()
            
            # Create notification for the user
            create_notification(
                user=user,
                title='Password Reset',
                message='Your password has been reset by an administrator. Please login with your new password.',
                notification_type='general'
            )
            
            messages.success(request, f'Password for "{user.username}" has been reset successfully.')
            return redirect('core:user_detail', user_id=user.id)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = PasswordResetForm()
    
    context = {
        'form': form,
        'viewed_user': user,
    }
    
    return render(request, 'core/user_management/user_reset_password.html', context)
