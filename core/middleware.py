# middleware.py
import datetime

from django.contrib import messages
from django.http import HttpResponseForbidden
from django.shortcuts import redirect, render
from django.utils import timezone

from .feature_access import (
    feature_denied_message,
    feature_denied_redirect_target,
    get_denied_feature_for_request,
)
from .settings_service import (
    get_clinic_settings,
    get_effective_session_timeout,
)
from .roles import role_matches
from .utils import is_profile_complete


class UserActivityMiddleware:
    """
    Middleware to track user last activity timestamp.
    Updates last_activity_at for authenticated users periodically.
    Uses the session to avoid hitting the database on every request.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            last_update = request.session.get('last_activity_update')
            now = timezone.now()
            if not last_update or (
                now - timezone.datetime.fromtimestamp(last_update, tz=datetime.timezone.utc)
            ).seconds > 300:
                User = __import__(
                    'django.contrib.auth', fromlist=['get_user_model']
                ).get_user_model()
                User.objects.filter(id=request.user.id).update(last_activity_at=now)
                request.session['last_activity_update'] = now.timestamp()

        return self.get_response(request)


class SessionTimeoutMiddleware:
    """Set session expiry from RoleSettings (see core.settings_service)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            if request.session.get('admin_session_persistent') is False:
                request.session.set_expiry(0)
            else:
                request.session.set_expiry(get_effective_session_timeout(request.user))

        return self.get_response(request)


class MaintenanceModeMiddleware:
    """
    When clinic maintenance mode is enabled, block non-admin users.
    Admins and auth/static paths remain available.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.exempt_prefixes = (
            '/static/',
            '/media/',
            '/accounts/',
            '/admin/',
            '/auth/admin-login/',
        )

    def __call__(self, request):
        try:
            clinic = get_clinic_settings()
        except Exception:
            return self.get_response(request)

        if not clinic.maintenance_mode:
            return self.get_response(request)

        if request.user.is_authenticated and getattr(request.user, 'role', None) == 'admin':
            return self.get_response(request)

        path = request.path
        if any(path.startswith(prefix) for prefix in self.exempt_prefixes):
            return self.get_response(request)

        message = clinic.maintenance_message or (
            'The clinic system is temporarily unavailable for maintenance. '
            'Please try again later.'
        )
        return render(
            request,
            'core/maintenance.html',
            {'maintenance_message': message, 'clinic_name': clinic.clinic_name},
            status=503,
        )


class RoleFeatureAccessMiddleware:
    """Block URLs when the user's role has the feature disabled in RoleSettings."""

    EXEMPT_PREFIXES = (
        '/static/',
        '/media/',
        '/accounts/',
        '/admin/',
        '/auth/admin-login/',
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        if not request.user.is_authenticated:
            return None
        path = request.path
        if any(path.startswith(prefix) for prefix in self.EXEMPT_PREFIXES):
            return None
        denied_flag = get_denied_feature_for_request(request)
        if denied_flag:
            messages.error(request, feature_denied_message(denied_flag))
            return redirect(feature_denied_redirect_target(request.user))
        return None


class RoleMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        return response

    def process_view(self, request, view_func, view_args, view_kwargs):
        if hasattr(view_func, 'required_roles'):
            if not request.user.is_authenticated:
                return HttpResponseForbidden()
            if not role_matches(request.user.role, *view_func.required_roles):
                return HttpResponseForbidden()


class ProfileCompleteMiddleware:
    """
    Middleware that blocks service access until required profile fields are complete.
    """

    def __init__(self, get_response):
        self.get_response = get_response

        self.exempt_urls = [
            '/profile/edit/',
            '/profile/required/',
            '/profile/preferences/',
            '/logout/',
        ]

        self.exempt_patterns = [
            '/media/',
            '/static/',
            '/accounts/',
            '/admin/',
        ]

    def __call__(self, request):
        if request.user.is_authenticated and not self._is_exempt_url(request.path):
            session_key = f'profile_complete_{request.user.id}_{request.user.role}'
            profile_complete = is_profile_complete(request.user)
            request.session[session_key] = profile_complete

            if not profile_complete:
                return redirect('core:profile_required')

        return self.get_response(request)

    def _is_exempt_url(self, path):
        if path in self.exempt_urls:
            return True
        return any(path.startswith(pattern) for pattern in self.exempt_patterns)
