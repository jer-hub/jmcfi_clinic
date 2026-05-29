"""In-app and email notification delivery respecting clinic and user preferences."""

from __future__ import annotations

import logging

from django.conf import settings
from django.core.mail import send_mail

from .settings_service import get_clinic_settings, get_user_preferences

logger = logging.getLogger(__name__)


def user_wants_email_notifications(user) -> bool:
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


def send_notification_email(user, subject: str, message: str) -> bool:
    """Send a plain-text notification email when clinic and user allow it."""
    if not clinic_allows_email_notifications():
        return False
    if not user_wants_email_notifications(user):
        return False

    clinic_name = 'JMCFI Clinic'
    try:
        clinic_name = get_clinic_settings().clinic_name or clinic_name
    except Exception:
        pass

    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', None) or 'noreply@localhost'
    full_subject = f'[{clinic_name}] {subject}'

    try:
        send_mail(
            full_subject,
            message,
            from_email,
            [user.email],
            fail_silently=False,
        )
        return True
    except Exception:
        logger.exception('Failed to send notification email to %s', user.email)
        return False


def notify_user(
    user,
    title: str,
    message: str,
    notification_type: str = 'general',
    related_id=None,
    transaction_type=None,
):
    """
    Deliver notification via in-app record and/or email per preferences.
    Returns the in-app Notification instance, or None if in-app is disabled.
    """
    from .utils import create_notification

    notification = create_notification(
        user,
        title,
        message,
        notification_type=notification_type,
        related_id=related_id,
        transaction_type=transaction_type,
    )
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
