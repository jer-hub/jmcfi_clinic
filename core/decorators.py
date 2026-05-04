# decorators.py
from functools import wraps
from django.http import HttpResponseForbidden
from django.shortcuts import redirect
from django.contrib import messages
from .utils import get_user_profile
from .profile_policy import (
    STUDENT_PROFILE_REQUIRED_FIELDS,
    STAFF_PROFILE_REQUIRED_FIELDS,
    DOCTOR_PROFILE_REQUIRED_FIELDS,
    ADMIN_PROFILE_REQUIRED_FIELDS,
)


CLINICAL_ADMIN_BLOCKED_NAMESPACES = {
    'health_forms_services',
}


def _blocks_admin_in_clinical_namespace(request, roles):
    if 'admin' not in roles or getattr(request.user, 'role', None) != 'admin':
        return False

    match = getattr(request, 'resolver_match', None)
    namespace = getattr(match, 'namespace', '') or ''
    return namespace in CLINICAL_ADMIN_BLOCKED_NAMESPACES

def role_required(*roles):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                messages.error(request, 'You must be logged in to access this page.')
                return redirect('account_login')

            if _blocks_admin_in_clinical_namespace(request, roles):
                messages.error(request, 'Admin access is not permitted for clinical application pages.')
                return redirect('core:dashboard')
            
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
            return redirect('core:admin_login')
        
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
        
        # Skip for superusers
        if request.user.is_superuser:
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
            return _is_student_profile_complete(user, profile)
        elif user.role == 'staff':
            return _is_staff_profile_complete(user, profile)
        elif user.role == 'doctor':
            return _is_doctor_profile_complete(user, profile)
        elif user.role == 'admin':
            return _is_admin_profile_complete(user, profile)
        
        return True
    except Exception:
        return False

def _is_student_profile_complete(user, profile):
    """Check if student profile is complete with all required fields"""
    for field in STUDENT_PROFILE_REQUIRED_FIELDS:
        value = getattr(user, field, None) if field in {'first_name', 'last_name'} else getattr(profile, field, None)
        if not value or (isinstance(value, str) and not value.strip()):
            return False
    
    return True

def _is_staff_profile_complete(user, profile):
    """Check if staff profile is complete with all required fields"""
    for field in STAFF_PROFILE_REQUIRED_FIELDS:
        value = getattr(user, field, None) if field in {'first_name', 'last_name'} else getattr(profile, field, None)
        if not value or (isinstance(value, str) and not value.strip()):
            return False

    return True


def _is_doctor_profile_complete(user, profile):
    """Check if doctor profile is complete with all required fields"""
    for field in DOCTOR_PROFILE_REQUIRED_FIELDS:
        value = getattr(user, field, None) if field in {'first_name', 'last_name'} else getattr(profile, field, None)
        if not value or (isinstance(value, str) and not value.strip()):
            return False

    return True


def _is_admin_profile_complete(user, profile):
    """Check if admin profile is complete with all required fields"""
    for field in ADMIN_PROFILE_REQUIRED_FIELDS:
        value = getattr(user, field, None) if field in {'first_name', 'last_name'} else getattr(profile, field, None)
        if not value or (isinstance(value, str) and not value.strip()):
            return False

    return True