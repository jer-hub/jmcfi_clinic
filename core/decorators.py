# decorators.py
from functools import wraps
from django.http import HttpResponseForbidden
from django.shortcuts import redirect
from django.contrib import messages
from .utils import get_user_profile

def role_required(*roles):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                messages.error(request, 'You must be logged in to access this page.')
                return redirect('account_login')
            
            if request.user.role not in roles:
                messages.error(request, f'Access denied. This page requires one of the following roles: {", ".join(roles)}. Your current role is: {request.user.role}.')
                return redirect('core:dashboard')
            return view_func(request, *args, **kwargs)
        wrapped_view.required_roles = roles
        return wrapped_view
    return decorator

def admin_required(view_func):
    """
    Decorator to ensure only admin users can access the view
    """
    @wraps(view_func)
    def wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, 'You must be logged in to access this page.')
            return redirect('account_login')
        
        if request.user.role != 'admin':
            messages.error(request, 'You do not have permission to access this page.')
            return redirect('core:dashboard')
        
        return view_func(request, *args, **kwargs)
    return wrapped_view

def profile_required(view_func):
    """
    Decorator to ensure user has completed their profile before accessing the view
    """
    @wraps(view_func)
    def wrapped_view(request, *args, **kwargs):
        # Skip if user is not authenticated
        if not request.user.is_authenticated:
            return redirect('account_login')
        
        # Skip for admin users
        if request.user.is_superuser or request.user.role == 'admin':
            return view_func(request, *args, **kwargs)

        # Check if profile is complete
        if not _is_profile_complete(request.user):
            messages.warning(request, 'Please complete your profile before accessing this page.')
            return redirect('core:edit_profile')
        
        return view_func(request, *args, **kwargs)
    return wrapped_view

def _is_profile_complete(user):
    """Check if user's profile is complete"""
    try:
        profile = get_user_profile(user)
        
        if not profile:
            return False

        if user.role == 'student':
            return _is_student_profile_complete(profile)
        elif user.role in ['staff', 'doctor']:
            return _is_staff_profile_complete(profile)
        
        return True
    except Exception:
        return False

def _is_student_profile_complete(profile):
    """Check if student profile is complete with all required fields"""
    required_fields = [
        'student_id', 'date_of_birth', 'phone', 
        'emergency_contact', 'emergency_phone', 'blood_type'
    ]
    
    for field in required_fields:
        value = getattr(profile, field, None)
        if not value or (isinstance(value, str) and not value.strip()):
            return False
    
    return True

def _is_staff_profile_complete(profile):
    """Check if staff profile is complete with all required fields"""
    required_fields = [
        'staff_id', 'department', 'phone'
    ]
    
    for field in required_fields:
        value = getattr(profile, field, None)
        if not value or (isinstance(value, str) and not value.strip()):
            return False
    
    return True