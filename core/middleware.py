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
    Middleware that blocks ALL service access for authenticated users who have
    not completed their required profile fields (including License Number and
    PTR No. for clinical staff/doctors).

    The check runs in __call__ so it covers every HTTP request – regular page
    loads, AJAX calls, form submissions, redirects – not just Django view
    functions.
    """

    def __init__(self, get_response):
        self.get_response = get_response

        # Exact URL paths that are always allowed (profile edit + auth flows)
        self.exempt_urls = [
            '/profile/edit/',
            '/profile/required/',
            '/logout/',
        ]

        # URL prefixes that are always allowed
        self.exempt_patterns = [
            '/media/',
            '/static/',
            '/accounts/',   # allauth: login, logout, signup, password-reset …
            '/admin/',      # Django admin (admins are already skipped by role)
        ]

    # ------------------------------------------------------------------
    # Primary intercept – runs on EVERY request
    # ------------------------------------------------------------------
    def __call__(self, request):
        if (
            request.user.is_authenticated
            and not request.user.is_superuser
            and getattr(request.user, 'role', None) != 'admin'
            and not self._is_exempt_url(request.path)
        ):
            # Session-cache the result to avoid a DB hit on every request
            session_key = f'profile_complete_{request.user.id}'
            profile_complete = request.session.get(session_key)

            if profile_complete is None:
                profile_complete = self._is_profile_complete(request.user)
                # Store without overriding the expiry set by SessionTimeoutMiddleware
                request.session[session_key] = profile_complete

            if not profile_complete:
                return redirect('core:profile_required')

        return self.get_response(request)

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
            'staff_id', 'department', 'phone',
            # Professional / licensing fields required for clinical staff
            'license_number', 'ptr_no',
        ]
        
        for field in required_fields:
            value = getattr(profile, field, None)
            if not value or (isinstance(value, str) and not value.strip()):
                return False
        
        return True