"""
HTMX-safe access denial helpers.

Use HX-Redirect on 401/403 for fragment requests so login/restricted pages are not
swapped into hx-target containers. Full-page visits use normal redirects.
"""

from __future__ import annotations

import json
from enum import Enum
from typing import Any
from urllib.parse import urlencode

from django.http import HttpResponse
from django.shortcuts import redirect
from django.urls import reverse

from .htmx_utils import is_htmx_request


class AccessReason(str, Enum):
    UNAUTHENTICATED = 'unauthenticated'
    FORBIDDEN = 'forbidden'
    CSRF = 'csrf'
    FEATURE_DISABLED = 'feature_disabled'
    CLINICAL_ADMIN_BLOCKED = 'clinical_admin_blocked'


RESTRICTED_ACCESS_URL_NAME = 'core:restricted_access'
LOGIN_URL_NAME = 'account_login'
ADMIN_LOGIN_URL_NAME = 'core:admin_login'


def _is_ajax_request(request) -> bool:
    return request.headers.get('X-Requested-With') == 'XMLHttpRequest'


def _safe_next_url(request, next_url: str | None = None) -> str:
    candidate = (next_url or getattr(request, 'get_full_path', lambda: '')() or '').strip()
    if not candidate or candidate.startswith('//'):
        return ''
    return candidate


def _reason_value(reason: str | AccessReason) -> str:
    if isinstance(reason, AccessReason):
        return reason.value
    return str(reason)


def restricted_access_url(
    *,
    reason: str | AccessReason = AccessReason.FORBIDDEN,
    next_url: str | None = None,
) -> str:
    params: dict[str, str] = {'reason': _reason_value(reason)}
    if next_url and next_url.strip() and not next_url.strip().startswith('//'):
        params['next'] = next_url.strip()
    base = reverse(RESTRICTED_ACCESS_URL_NAME)
    return f'{base}?{urlencode(params)}'


def login_redirect_url(request, *, admin: bool = False) -> str:
    """Login URL with optional ?next= for post-auth return."""
    url_name = ADMIN_LOGIN_URL_NAME if admin else LOGIN_URL_NAME
    base = reverse(url_name)
    nxt = _safe_next_url(request)
    if not nxt:
        return base
    return f'{base}?{urlencode({"next": nxt})}'


def access_denied_response(
    request,
    *,
    status_code: int,
    reason: str | AccessReason,
    message: str | None = None,
    use_admin_login: bool = False,
    redirect_url: str | None = None,
) -> HttpResponse:
    """
    Return HTMX-safe denial (401/403 + HX-Redirect) or a full-page redirect.

    HX-Redirect is preferred over an in-page modal for auth failures: Google OAuth
    and admin password login require a full navigation, not a fragment swap.
    """
    reason_value = _reason_value(reason)
    if redirect_url:
        target = redirect_url
    elif status_code == 401 or reason_value == AccessReason.UNAUTHENTICATED.value:
        target = login_redirect_url(request, admin=use_admin_login)
    else:
        target = restricted_access_url(
            reason=reason_value,
            next_url=_safe_next_url(request),
        )

    if is_htmx_request(request) or _is_ajax_request(request):
        response = HttpResponse(status=status_code)
        response['HX-Redirect'] = target
        response['HX-Trigger'] = json.dumps({
            'access-denied': {
                'reason': reason_value,
                'status': status_code,
                'message': message or '',
                'redirect': target,
            },
        })
        if message:
            response['X-Access-Denied-Message'] = message[:500]
        response['X-Access-Denied-Reason'] = reason_value
        return response

    return redirect(target)


def access_denied_json_or_htmx(
    request,
    *,
    status_code: int,
    reason: str | AccessReason,
    error: str,
    use_admin_login: bool = False,
) -> HttpResponse:
    """Backward-compatible helper for views that returned JsonResponse errors."""
    if is_htmx_request(request):
        return access_denied_response(
            request,
            status_code=status_code,
            reason=reason,
            message=error,
            use_admin_login=use_admin_login,
        )

    from django.http import JsonResponse

    return JsonResponse({'success': False, 'error': error}, status=status_code)


def restricted_access_context(request) -> dict[str, Any]:
    """Build template context for the restricted access page."""
    from .utils import role_home_url_name

    reason = request.GET.get('reason', AccessReason.FORBIDDEN.value)
    next_url = _safe_next_url(request, request.GET.get('next'))
    is_authenticated = request.user.is_authenticated

    copy = {
        AccessReason.UNAUTHENTICATED.value: {
            'title': 'Sign in required',
            'headline': 'You need to sign in',
            'body': 'This page is only available to signed-in clinic users.',
            'icon': 'fa-lock',
            'icon_bg': 'bg-primary-100 text-primary-600',
        },
        AccessReason.FORBIDDEN.value: {
            'title': 'Restricted access',
            'headline': 'You do not have permission',
            'body': 'Your account cannot open this page. Contact your clinic administrator if you believe this is a mistake.',
            'icon': 'fa-shield-halved',
            'icon_bg': 'bg-warning-100 text-warning-700',
        },
        AccessReason.CSRF.value: {
            'title': 'Session expired',
            'headline': 'Security check failed',
            'body': 'Your session may have expired or this form was open too long. Refresh the page and try again.',
            'icon': 'fa-clock-rotate-left',
            'icon_bg': 'bg-danger-100 text-danger-600',
        },
        AccessReason.FEATURE_DISABLED.value: {
            'title': 'Feature unavailable',
            'headline': 'Not enabled for your role',
            'body': 'This feature is turned off for your account type. Ask an administrator to update role settings if you need access.',
            'icon': 'fa-toggle-off',
            'icon_bg': 'bg-muted-100 text-muted-600',
        },
        AccessReason.CLINICAL_ADMIN_BLOCKED.value: {
            'title': 'Clinical area restricted',
            'headline': 'Admin access not permitted here',
            'body': 'Administrator accounts cannot use clinical workflow pages. Use the admin dashboard or assign a clinical role.',
            'icon': 'fa-user-doctor',
            'icon_bg': 'bg-info-100 text-info-700',
        },
    }

    detail = dict(copy.get(reason, copy[AccessReason.FORBIDDEN.value]))
    home_url = None
    user_role = getattr(request.user, 'role', '') if is_authenticated else ''
    is_admin = is_authenticated and user_role == 'admin'

    if is_authenticated:
        try:
            home_url = reverse(role_home_url_name(request.user))
        except Exception:
            home_url = reverse('core:dashboard')

    if is_admin and reason == AccessReason.FORBIDDEN.value:
        detail['body'] = (
            'This page is limited to clinical staff roles. '
            'Use the admin dashboard to manage users, analytics, and clinic settings.'
        )

    return {
        'access_reason': reason,
        'access_next': next_url,
        'access_is_authenticated': is_authenticated,
        'access_is_admin': is_admin,
        'access_user_role': user_role,
        'access_home_url': home_url,
        'access_login_url': login_redirect_url(request),
        'access_admin_login_url': reverse(ADMIN_LOGIN_URL_NAME),
        'access_show_admin_signin_footer': not is_authenticated,
        **detail,
    }
