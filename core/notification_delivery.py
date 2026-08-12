"""In-app and email notification delivery respecting clinic and user preferences."""

from __future__ import annotations

import logging
import smtplib

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, send_mail
from django.template.loader import render_to_string

from .settings_service import get_clinic_settings, get_user_preferences
from .guest_auth import is_guest_user, resolve_patient_contact_email

logger = logging.getLogger(__name__)


def format_email_send_error(exc: BaseException) -> str:
    """Human-readable SMTP/config error for staff flash messages."""
    if isinstance(exc, smtplib.SMTPAuthenticationError):
        return (
            'SMTP login failed. For Gmail, set EMAIL_HOST_PASSWORD to a Google App Password '
            '(not your normal account password). See https://support.google.com/accounts/answer/185833'
        )
    if isinstance(exc, smtplib.SMTPSenderRefused):
        return (
            f'Sender rejected by SMTP. Set DEFAULT_FROM_EMAIL to match EMAIL_HOST_USER '
            f'({getattr(settings, "EMAIL_HOST_USER", "") or "your SMTP mailbox"}).'
        )
    if isinstance(exc, (smtplib.SMTPException, OSError)):
        return f'SMTP error: {exc}'
    return str(exc) or exc.__class__.__name__

def user_wants_email_notifications(user) -> bool:
    if not user:
        return False
    # Guests never authenticate; allow email when contact_email is present.
    if is_guest_user(user):
        return bool(resolve_patient_contact_email(user))
    if not getattr(user, 'is_authenticated', False):
        return False
    if not (getattr(user, 'email', None) or '').strip():
        return False
    try:
        return get_user_preferences(user).email_notifications
    except Exception:
        return True


def clinic_allows_email_notifications() -> bool:
    try:
        return get_clinic_settings().enable_email_notifications
    except Exception:
        return False


def _clinic_name() -> str:
    try:
        return get_clinic_settings().clinic_name or 'JMCFI Clinic'
    except Exception:
        return 'JMCFI Clinic'


def send_notification_email(user, subject: str, message: str) -> bool:
    """Send a plain-text notification email when clinic and user allow it."""
    if not clinic_allows_email_notifications():
        return False
    if not user_wants_email_notifications(user):
        return False

    to_email = resolve_patient_contact_email(user)
    if not to_email:
        return False

    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', None) or 'noreply@localhost'
    full_subject = f'[{_clinic_name()}] {subject}'

    try:
        send_mail(
            full_subject,
            message,
            from_email,
            [to_email],
            fail_silently=False,
        )
        return True
    except Exception:
        logger.exception('Failed to send notification email to %s', to_email)
        return False


def send_templated_email(
    user,
    subject: str,
    template_base: str,
    context: dict,
    *,
    raise_on_error: bool = False,
) -> bool:
    """
    Send HTML+text email using templates named `{template_base}.txt` and `.html`.
    Guests use contact_email; others use User.email.
    """
    if not clinic_allows_email_notifications():
        if raise_on_error:
            raise RuntimeError(
                'Clinic email notifications are turned off. '
                'Enable them under Clinic Settings → Notifications.'
            )
        return False

    to_email = resolve_patient_contact_email(user)
    if not to_email:
        if raise_on_error:
            raise RuntimeError('No contact email is available for this patient.')
        return False

    # Non-guest patients still respect email preference.
    if not is_guest_user(user) and not user_wants_email_notifications(user):
        if raise_on_error:
            raise RuntimeError(
                'This patient has email notifications disabled in their preferences.'
            )
        return False

    ctx = {
        'clinic_name': _clinic_name(),
        'user': user,
        **(context or {}),
    }
    text_body = render_to_string(f'{template_base}.txt', ctx)
    html_body = render_to_string(f'{template_base}.html', ctx)
    # Gmail requires From to be the authenticated mailbox (or an allowed alias).
    host_user = (getattr(settings, 'EMAIL_HOST_USER', None) or '').strip()
    configured_from = (getattr(settings, 'DEFAULT_FROM_EMAIL', None) or '').strip()
    from_email = host_user or configured_from or 'noreply@localhost'
    full_subject = f'[{ctx["clinic_name"]}] {subject}'

    try:
        msg = EmailMultiAlternatives(full_subject, text_body, from_email, [to_email])
        msg.attach_alternative(html_body, 'text/html')
        msg.send(fail_silently=False)
        return True
    except Exception as exc:
        logger.exception('Failed to send templated email to %s', to_email)
        if raise_on_error:
            raise
        return False

def notify_user(
    user,
    title: str,
    message: str,
    notification_type: str = 'general',
    related_id=None,
    transaction_type=None,
    *,
    skip_in_app_for_guest: bool = True,
    send_email: bool = True,
):
    """
    Deliver notification via in-app record and/or email per preferences.
    Returns the in-app Notification instance, or None if in-app is skipped/disabled.
    """
    from .utils import create_notification

    notification = None
    if not (skip_in_app_for_guest and is_guest_user(user)):
        notification = create_notification(
            user,
            title,
            message,
            notification_type=notification_type,
            related_id=related_id,
            transaction_type=transaction_type,
        )
    if send_email:
        send_notification_email(user, title, message)
    return notification


def resolve_system_notification_recipients(recipient_type: str):
    """Return a User queryset for admin broadcast recipient selection."""
    from .models import User
    from .roles import PATIENT_ROLE_VALUES

    if recipient_type == 'students':
        return User.objects.filter(role__in=PATIENT_ROLE_VALUES)
    if recipient_type == 'staff_only':
        return User.objects.filter(role='staff')
    if recipient_type == 'doctors':
        return User.objects.filter(role='doctor')
    if recipient_type == 'admins':
        return User.objects.filter(role='admin')
    if recipient_type == 'staff_and_doctors':
        return User.objects.filter(role__in=['staff', 'doctor'])
    if recipient_type == 'non_students':
        return User.objects.filter(role__in=['staff', 'doctor', 'admin'])
    return User.objects.filter(role__in=[*PATIENT_ROLE_VALUES, 'staff', 'doctor', 'admin'])


def deliver_bulk_notifications(
    users,
    title: str,
    message: str,
    notification_type: str = 'general',
    related_id=None,
    transaction_type=None,
):
    """In-app bulk create plus optional email per recipient."""
    from .utils import create_bulk_notifications

    created = create_bulk_notifications(
        users,
        title,
        message,
        notification_type=notification_type,
        related_id=related_id,
        transaction_type=transaction_type,
    )
    for user in users:
        send_notification_email(user, title, message)
    return created
