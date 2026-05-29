# decorators.py
from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect

from .access_control import AccessReason, access_denied_response
from .htmx_utils import is_htmx_request
from .roles import role_matches
from .settings_service import admin_blocks_clinical_namespaces
from .utils import is_profile_complete, role_home_url_name

CLINICAL_ADMIN_BLOCKED_NAMESPACES = {
    'health_forms_services',
}


def _blocks_admin_in_clinical_namespace(request, roles):
    if 'admin' not in roles or getattr(request.user, 'role', None) != 'admin':
        return False
    if not admin_blocks_clinical_namespaces():
        return False

    match = getattr(request, 'resolver_match', None)
    namespace = getattr(match, 'namespace', '') or ''
    return namespace in CLINICAL_ADMIN_BLOCKED_NAMESPACES


def role_required(*roles):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                if not is_htmx_request(request):
                    messages.error(request, 'You must be logged in to access this page.')
                return access_denied_response(
                    request,
                    status_code=401,
                    reason=AccessReason.UNAUTHENTICATED,
                )

            if _blocks_admin_in_clinical_namespace(request, roles):
                return access_denied_response(
                    request,
                    status_code=403,
                    reason=AccessReason.CLINICAL_ADMIN_BLOCKED,
                )

            if not role_matches(request.user.role, *roles):
                return access_denied_response(
                    request,
                    status_code=403,
                    reason=AccessReason.FORBIDDEN,
                )
            return view_func(request, *args, **kwargs)

        wrapped_view.required_roles = roles
        return wrapped_view

    return decorator


def admin_required(view_func):
    """Decorator to ensure only admin users can access the view."""

    @wraps(view_func)
    def wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            if not is_htmx_request(request):
                messages.error(request, 'You must be logged in to access this page.')
            return access_denied_response(
                request,
                status_code=401,
                reason=AccessReason.UNAUTHENTICATED,
                use_admin_login=True,
            )

        if request.user.role != 'admin':
            return access_denied_response(
                request,
                status_code=403,
                reason=AccessReason.FORBIDDEN,
            )

        return view_func(request, *args, **kwargs)

    return wrapped_view


def profile_required(view_func):
    """Ensure the user has completed their profile before accessing the view."""

    @wraps(view_func)
    def wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return access_denied_response(
                request,
                status_code=401,
                reason=AccessReason.UNAUTHENTICATED,
            )

        if request.user.is_superuser:
            return view_func(request, *args, **kwargs)

        if not is_profile_complete(request.user):
            messages.warning(
                request,
                'Please complete your profile before accessing this page.',
            )
            return redirect('core:profile_required')

        return view_func(request, *args, **kwargs)

    return wrapped_view


def htmx_login_required(view_func):
    """Drop-in replacement for @login_required with HTMX-safe 401 responses."""

    @wraps(view_func)
    def wrapped_view(request, *args, **kwargs):
        if request.user.is_authenticated:
            return view_func(request, *args, **kwargs)
        return access_denied_response(
            request,
            status_code=401,
            reason=AccessReason.UNAUTHENTICATED,
        )

    return wrapped_view
