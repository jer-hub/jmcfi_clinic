"""Authentication, health probes, and access-control views."""

import hashlib
import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.core.cache import cache
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods

from core.forms import AdminLoginForm
from core.models import UserInvite
from core.notification_delivery import notify_user
from core.settings_service import get_effective_session_timeout
from core.views.helpers import _get_client_ip, _hash_invite_token

User = get_user_model()
ADMIN_LOGIN_ATTEMPT_LIMIT = 5
ADMIN_LOGIN_LOCK_SECONDS = 900
auth_logger = logging.getLogger('security.auth')


def _admin_login_cache_key(request, email):
    fingerprint = f"{_get_client_ip(request)}:{(email or '').strip().lower()}"
    digest = hashlib.sha256(fingerprint.encode('utf-8')).hexdigest()
    return f"admin_login_failures:{digest}"


def _safe_login_redirect(request, target_url, user=None):
    require_https = bool(
        getattr(settings, 'ADMIN_LOGIN_REQUIRE_HTTPS_REDIRECT', False)
        or request.is_secure()
    )
    if target_url and url_has_allowed_host_and_scheme(
        url=target_url,
        allowed_hosts={request.get_host()},
        require_https=require_https,
    ):
        return target_url
    from core.utils import role_home_url
    home_user = user if user is not None else request.user
    return role_home_url(home_user)


def health_check(request):
    """Lightweight liveness probe for managed platforms."""
    return JsonResponse({"status": "ok"})


def health_ready(request):
    """Readiness probe that verifies database connectivity."""
    from django.db import connection

    try:
        connection.ensure_connection()
    except Exception:
        return JsonResponse(
            {"status": "error", "database": "unavailable"},
            status=503,
        )
    return JsonResponse({"status": "ok", "database": "connected"})


@require_http_methods(["GET", "POST"])
def admin_login(request):
    """Dedicated password login endpoint for admin-role accounts."""
    if request.user.is_authenticated:
        from core.utils import role_home_url_name
        return redirect(role_home_url_name(request.user))

    requested_next = request.GET.get('next') if request.method == 'GET' else request.POST.get('next')
    redirect_to = _safe_login_redirect(request, requested_next)
    form = AdminLoginForm(request.POST or None)

    if request.method == 'POST':
        attempted_email = (request.POST.get('email') or '').strip().lower()
        client_ip = _get_client_ip(request)
        throttle_key = _admin_login_cache_key(request, attempted_email)
        failure_count = cache.get(throttle_key, 0)

        if failure_count >= ADMIN_LOGIN_ATTEMPT_LIMIT:
            auth_logger.warning(
                'admin_login_lockout_active email=%s ip=%s failures=%s',
                attempted_email,
                client_ip,
                failure_count,
            )
            form.add_error(None, 'Too many failed attempts. Try again in 15 minutes.')
        elif form.is_valid():
            credentials = {
                User.USERNAME_FIELD: form.cleaned_data['email'],
                'password': form.cleaned_data['password'],
            }
            user = authenticate(request, **credentials)

            is_admin_user = bool(
                user
                and user.is_active
                and (user.is_superuser or user.role == User.ROLE.ADMIN)
            )

            if not is_admin_user:
                updated_failures = failure_count + 1
                cache.set(throttle_key, updated_failures, ADMIN_LOGIN_LOCK_SECONDS)
                auth_logger.warning(
                    'admin_login_failed email=%s ip=%s failures=%s user_found=%s role=%s',
                    attempted_email,
                    client_ip,
                    updated_failures,
                    bool(user),
                    getattr(user, 'role', ''),
                )
                if updated_failures >= ADMIN_LOGIN_ATTEMPT_LIMIT:
                    auth_logger.warning(
                        'admin_login_lockout_triggered email=%s ip=%s failures=%s lock_seconds=%s',
                        attempted_email,
                        client_ip,
                        updated_failures,
                        ADMIN_LOGIN_LOCK_SECONDS,
                    )
                form.add_error(None, 'Invalid admin credentials.')
            else:
                cache.delete(throttle_key)
                login(request, user)
                remember_me = bool(form.cleaned_data.get('remember_me'))
                auth_logger.info(
                    'admin_login_success user_id=%s email=%s ip=%s remember_me=%s',
                    user.id,
                    user.email,
                    client_ip,
                    remember_me,
                )
                if remember_me:
                    request.session['admin_session_persistent'] = True
                    request.session.set_expiry(get_effective_session_timeout(user))
                else:
                    request.session['admin_session_persistent'] = False
                    request.session.set_expiry(0)
                return redirect(_safe_login_redirect(request, requested_next, user=user))

    return render(
        request,
        'core/admin_login.html',
        {
            'form': form,
            'next': redirect_to,
        },
    )


def logout_view(request):
    """Handle user logout"""
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('account_login')


def restricted_access(request):
    """Full-page restricted / unauthorized access display (also HX-Redirect target)."""
    from django.contrib import messages

    from core.access_control import restricted_access_context

    # Page copy already explains denial; do not also flash the same text as a toast.
    list(messages.get_messages(request))

    return render(
        request,
        'core/restricted_access.html',
        restricted_access_context(request),
    )


def csrf_failure(request, reason=''):
    """CSRF verification failed — HTMX-safe redirect to restricted access page."""
    from core.access_control import AccessReason, access_denied_response, restricted_access_context
    from core.htmx_utils import is_htmx_request

    if is_htmx_request(request) or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return access_denied_response(
            request,
            status_code=403,
            reason=AccessReason.CSRF,
        )

    context = restricted_access_context(request)
    context['csrf_failure_reason'] = reason
    return render(request, 'core/restricted_access.html', context, status=403)


@require_http_methods(["GET", "POST"])
def accept_invite(request, token):
    """Accept a user invitation and activate account when invite is valid."""
    invite = UserInvite.objects.select_related('user').filter(
        token_hash=_hash_invite_token(token)
    ).first()

    if not invite:
        return render(request, 'core/invite_accept.html', {'invite_state': 'invalid'})

    user = invite.user
    now = timezone.now()

    if invite.revoked_at:
        return render(request, 'core/invite_accept.html', {'invite_state': 'revoked'})
    if invite.accepted_at:
        return render(request, 'core/invite_accept.html', {'invite_state': 'accepted', 'invited_user': user})
    if invite.expires_at <= now:
        return render(request, 'core/invite_accept.html', {'invite_state': 'expired', 'invited_user': user})
    if user.onboarding_status == User.ONBOARDING_STATUS.ACTIVE and user.is_active:
        return render(request, 'core/invite_accept.html', {'invite_state': 'already_active', 'invited_user': user})

    if request.method == 'POST':
        with transaction.atomic():
            invite.accepted_at = now
            invite.save(update_fields=['accepted_at', 'updated_at'])
            UserInvite.objects.filter(
                user=user,
                accepted_at__isnull=True,
                revoked_at__isnull=True,
            ).exclude(pk=invite.pk).update(revoked_at=now)

            user.is_active = True
            user.onboarding_status = User.ONBOARDING_STATUS.ACTIVE
            user.save(update_fields=['is_active', 'onboarding_status'])

            notify_user(
                user=user,
                title='Invitation Accepted',
                message='Your account invitation has been accepted and your account is now active.',
                notification_type='general'
            )

        messages.success(request, 'Invitation accepted. You can now sign in.')
        return redirect('account_login')

    context = {
        'invite_state': 'ready',
        'invited_user': user,
        'expires_at': invite.expires_at,
    }
    return render(request, 'core/invite_accept.html', context)
