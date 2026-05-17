# decorators.py
from functools import wraps

from django.contrib import messages
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import redirect

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
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse(
                        {'success': False, 'error': 'Authentication required.'},
                        status=401,
                    )
                messages.error(request, 'You must be logged in to access this page.')
                return redirect('account_login')

            if _blocks_admin_in_clinical_namespace(request, roles):
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse(
                        {
                            'success': False,
                            'error': 'Admin access is not permitted for clinical application pages.',
                        },
                        status=403,
                    )
                messages.error(
                    request,
                    'Admin access is not permitted for clinical application pages.',
                )
                return redirect(role_home_url_name(request.user))

            if not role_matches(request.user.role, *roles):
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse(
                        {
                            'success': False,
                            'error': f'Access denied. Required role(s): {", ".join(roles)}.',
                        },
                        status=403,
                    )
                messages.error(request, 'Access denied. You do not have permission to access this page.')
                return redirect(role_home_url_name(request.user))
            return view_func(request, *args, **kwargs)

        wrapped_view.required_roles = roles
        return wrapped_view

    return decorator


def admin_required(view_func):
    """Decorator to ensure only admin users can access the view."""

    @wraps(view_func)
    def wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, 'You must be logged in to access this page.')
            return redirect('core:admin_login')

        if request.user.role != 'admin':
            messages.error(request, 'You do not have permission to access this page.')
            return redirect(role_home_url_name(request.user))

        return view_func(request, *args, **kwargs)

    return wrapped_view


def profile_required(view_func):
    """Ensure the user has completed their profile before accessing the view."""

    @wraps(view_func)
    def wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('account_login')

        if request.user.is_superuser:
            return view_func(request, *args, **kwargs)

        if not is_profile_complete(request.user):
            messages.warning(request, 'Please complete your profile before accessing this page.')
            return redirect('core:edit_profile')

        return view_func(request, *args, **kwargs)

    return wrapped_view
