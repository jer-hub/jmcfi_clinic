"""Magic-link guest access tokens for guest patients."""

from __future__ import annotations

import hashlib
import logging
import secrets

from django.conf import settings
from django.urls import reverse
from django.utils import timezone

from .models import GuestAccessToken

logger = logging.getLogger(__name__)

GUEST_ACCESS_TOKEN_TTL_HOURS = getattr(settings, 'GUEST_ACCESS_TOKEN_TTL_HOURS', 72)


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode('utf-8')).hexdigest()


def issue_guest_access_token(user, purpose: str, object_id: int, *, created_by=None):
    """
    Create a new guest token; revoke any prior active token for the same target.
    Returns (GuestAccessToken, raw_token).
    """
    now = timezone.now()
    GuestAccessToken.objects.filter(
        user=user,
        purpose=purpose,
        object_id=object_id,
        revoked_at__isnull=True,
    ).update(revoked_at=now)

    raw_token = secrets.token_urlsafe(32)
    token = GuestAccessToken.objects.create(
        user=user,
        purpose=purpose,
        object_id=int(object_id),
        token_hash=_hash_token(raw_token),
        created_by=created_by if getattr(created_by, 'pk', None) else None,
        expires_at=now + timezone.timedelta(hours=GUEST_ACCESS_TOKEN_TTL_HOURS),
    )
    return token, raw_token


def validate_guest_token(raw_token: str, purpose: str):
    """Return active GuestAccessToken for raw token + purpose, or None."""
    raw = (raw_token or '').strip()
    if not raw or purpose not in GuestAccessToken.Purpose.values:
        return None
    token = (
        GuestAccessToken.objects.select_related('user', 'user__patient_profile')
        .filter(
            token_hash=_hash_token(raw),
            purpose=purpose,
            revoked_at__isnull=True,
        )
        .first()
    )
    if not token:
        return None
    if token.expires_at <= timezone.now():
        return None
    return token


def mark_guest_token_used(token: GuestAccessToken):
    if token.used_at:
        return
    token.used_at = timezone.now()
    token.save(update_fields=['used_at', 'updated_at'])


def revoke_guest_token(token: GuestAccessToken):
    if token.revoked_at:
        return
    token.revoked_at = timezone.now()
    token.save(update_fields=['revoked_at', 'updated_at'])


def guest_url_name_for_purpose(purpose: str) -> str:
    if purpose == GuestAccessToken.Purpose.APPOINTMENT:
        return 'core:guest_appointment'
    if purpose == GuestAccessToken.Purpose.HEALTH_FORM:
        return 'core:guest_health_form'
    if purpose == GuestAccessToken.Purpose.MEDICAL_RECORD:
        return 'core:guest_medical_record'
    if purpose == GuestAccessToken.Purpose.DENTAL_INTAKE:
        return 'core:guest_dental_intake'
    if purpose == GuestAccessToken.Purpose.DENTAL_RECORD:
        return 'core:guest_dental_record'
    raise ValueError(f'Unknown guest purpose: {purpose}')


def build_guest_url(request, purpose: str, raw_token: str) -> str:
    """Absolute URL for a guest magic link."""
    path = reverse(guest_url_name_for_purpose(purpose), kwargs={'token': raw_token})
    if request is not None:
        try:
            return request.build_absolute_uri(path)
        except Exception:
            logger.warning(
                'build_absolute_uri failed for guest link; falling back to SITE_URL',
                exc_info=True,
            )
    site_url = (getattr(settings, 'SITE_URL', None) or '').rstrip('/')
    if site_url:
        return f'{site_url}{path}'
    # Last-resort relative path (still usable if opened from same origin later).
    return path
