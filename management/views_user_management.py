# User Management Views (Admin Only)
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.contrib.auth import get_user_model
from core.decorators import admin_required
from management.forms_user_management import UserCreationForm, UserEditForm, PasswordResetForm
from management.models import (
    Appointment, MedicalRecord, CertificateRequest,
    StudentProfile, StaffProfile
)
from management.utils import create_notification, get_user_profile, paginate_queryset

User = get_user_model()


@login_required
@admin_required
def user_management(request):
    """List all users with filtering and search"""
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
    
    return render(request, 'management/user_management/user_list.html', context)


@login_required
@admin_required
def user_detail(request, user_id):
    """View detailed information about a specific user"""
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
    
    return render(request, 'management/user_management/user_detail.html', context)


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
            return redirect('management:user_detail', user_id=user.id)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = UserCreationForm()
    
    context = {
        'form': form,
        'action': 'Create',
    }
    
    return render(request, 'management/user_management/user_form.html', context)


@login_required
@admin_required
def user_edit(request, user_id):
    """Edit an existing user"""
    user = get_object_or_404(User, id=user_id)
    
    # Prevent editing admin users
    if user.role == 'admin':
        messages.error(request, 'Cannot edit admin users.')
        return redirect('management:user_detail', user_id=user.id)
    
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
            return redirect('management:user_detail', user_id=user.id)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = UserEditForm(instance=user)
    
    context = {
        'form': form,
        'action': 'Edit',
        'viewed_user': user,
    }
    
    return render(request, 'management/user_management/user_form.html', context)


@login_required
@admin_required
def user_delete(request, user_id):
    """Delete a user"""
    user = get_object_or_404(User, id=user_id)
    
    # Prevent deleting admin users
    if user.role == 'admin':
        messages.error(request, 'Cannot delete admin users.')
        return redirect('management:user_detail', user_id=user.id)
    
    # Prevent deleting self
    if user.id == request.user.id:
        messages.error(request, 'Cannot delete your own account.')
        return redirect('management:user_detail', user_id=user.id)
    
    if request.method == 'POST':
        username = user.username
        user.delete()
        messages.success(request, f'User "{username}" has been deleted.')
        return redirect('management:user_management')
    
    context = {
        'viewed_user': user,
    }
    
    return render(request, 'management/user_management/user_delete_confirm.html', context)


@login_required
@admin_required
def user_toggle_status(request, user_id):
    """Toggle user active/inactive status"""
    user = get_object_or_404(User, id=user_id)
    
    # Prevent deactivating admin users
    if user.role == 'admin':
        messages.error(request, 'Cannot deactivate admin users.')
        return redirect('management:user_detail', user_id=user.id)
    
    # Prevent deactivating self
    if user.id == request.user.id:
        messages.error(request, 'Cannot deactivate your own account.')
        return redirect('management:user_detail', user_id=user.id)
    
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
    
    return redirect('management:user_detail', user_id=user.id)


@login_required
@admin_required
def user_reset_password(request, user_id):
    """Reset user password"""
    user = get_object_or_404(User, id=user_id)
    
    # Prevent resetting admin passwords
    if user.role == 'admin':
        messages.error(request, 'Cannot reset admin user passwords.')
        return redirect('management:user_detail', user_id=user.id)
    
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
            return redirect('management:user_detail', user_id=user.id)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = PasswordResetForm()
    
    context = {
        'form': form,
        'viewed_user': user,
    }
    
    return render(request, 'management/user_management/user_reset_password.html', context)
