# middleware.py
from django.http import HttpResponseForbidden
from django.shortcuts import redirect
from django.urls import reverse
from django.contrib import messages
from django.conf import settings
from .utils import get_user_profile


class SessionTimeoutMiddleware:
    """
    Middleware to set role-specific session timeouts
    Admin: 12 hours
    Staff: 24 hours  
    Student: 24 hours
    """
    def __init__(self, get_response):
        self.get_response = get_response
        # Define session timeouts in seconds
        self.role_timeouts = {
            'admin': 43200,    # 12 hours
            'doctor': 86400,   # 24 hours
            'staff': 86400,    # 24 hours
            'student': 86400,  # 24 hours
        }

    def __call__(self, request):
        # Set session timeout based on user role
        if request.user.is_authenticated:
            user_role = getattr(request.user, 'role', None)
            if user_role in self.role_timeouts:
                timeout = self.role_timeouts[user_role]
                request.session.set_expiry(timeout)
        
        response = self.get_response(request)
        return response


class RoleMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        return response

    def process_view(self, request, view_func, view_args, view_kwargs):
        if hasattr(view_func, 'required_roles'):
            # Skip check if user is not authenticated
            if not request.user.is_authenticated:
                return HttpResponseForbidden()
            if request.user.role not in view_func.required_roles:
                return HttpResponseForbidden()


class ProfileCompleteMiddleware:
    """
    Middleware to ensure users complete their profile before accessing protected pages
    """
    def __init__(self, get_response):
        self.get_response = get_response
        # URLs that don't require profile completion - only essential pages
        self.exempt_urls = [
            '/profile/edit/',
            '/profile/required/',
            '/logout/',
        ]
        # Add media and static URLs
        self.exempt_patterns = [
            '/media/',
            '/static/',
        ]

    def __call__(self, request):
        response = self.get_response(request)
        return response

    def process_view(self, request, view_func, view_args, view_kwargs):
        # Skip if user is not authenticated
        if not request.user.is_authenticated:
            return None

        # Skip for admin users
        if request.user.is_superuser or request.user.role == 'admin':
            return None

        # Skip if accessing exempt URLs
        if self._is_exempt_url(request.path):
            return None

        # Check session cache first to avoid repeated database calls
        session_key = f'profile_complete_{request.user.id}'
        profile_complete = request.session.get(session_key)
        
        # If not in session or it's been a while, check the database
        if profile_complete is None:
            profile_complete = self._is_profile_complete(request.user)
            request.session[session_key] = profile_complete
            # Cache for 5 minutes
            request.session.set_expiry(300)

        # Check if profile is complete
        if not profile_complete:
            # If already on profile edit page, don't redirect
            if request.path == '/profile/edit/':
                return None
            
            # Silent redirect - the banner will handle the messaging
            return redirect('core:profile_required')

        return None

    def _is_exempt_url(self, path):
        """Check if the URL is exempt from profile completion requirement"""
        # Check exact matches
        if path in self.exempt_urls:
            return True

        # Check pattern matches
        for pattern in self.exempt_patterns:
            if path.startswith(pattern):
                return True
                
        return False

    def _is_profile_complete(self, user):
        """Check if user's profile is complete"""
        try:
            profile = get_user_profile(user)
            
            if not profile:
                return False

            if user.role == 'student':
                return self._is_student_profile_complete(profile)
            elif user.role in ['staff', 'doctor']:
                return self._is_staff_profile_complete(profile)
            
            return True
        except Exception:
            return False

    def _is_student_profile_complete(self, profile):
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

    def _is_staff_profile_complete(self, profile):
        """Check if staff profile is complete with all required fields"""
        required_fields = [
            'staff_id', 'department', 'phone'
        ]
        
        for field in required_fields:
            value = getattr(profile, field, None)
            if not value or (isinstance(value, str) and not value.strip()):
                return False
        
        return True