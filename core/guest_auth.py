"""Staff-created clinic guest patients — no self-service login."""

from __future__ import annotations

import uuid
from datetime import date

from django.contrib.auth import get_user_model

from .models import PatientProfile
from .roles import ROLE_PATIENT

User = get_user_model()

GUEST_EMAIL_DOMAIN = 'guest.local'
LEGACY_GUEST_EMAIL_DOMAIN = 'walkin.local'
GUEST_INSTITUTIONAL_FIELDS = frozenset({'department', 'course', 'year_level'})


def is_guest_user(user) -> bool:
    """True for clinic-managed guests (*@guest.local or legacy *@walkin.local)."""
    email = getattr(user, 'email', None) or ''
    lower = email.lower()
    return lower.endswith(f'@{GUEST_EMAIL_DOMAIN}') or lower.endswith(
        f'@{LEGACY_GUEST_EMAIL_DOMAIN}'
    )


def exclude_guest_users(queryset):
    """Drop clinic guest accounts from a User queryset (picker search, etc.)."""
    from django.db.models import Q

    return queryset.exclude(
        Q(email__iendswith=f'@{GUEST_EMAIL_DOMAIN}')
        | Q(email__iendswith=f'@{LEGACY_GUEST_EMAIL_DOMAIN}')
    )


def resolve_patient_contact_email(user) -> str:
    """
    Real address for outbound email.
    Guests use PatientProfile.contact_email; others use User.email.
    """
    if not user:
        return ''
    if is_guest_user(user):
        try:
            profile = user.patient_profile
        except PatientProfile.DoesNotExist:
            return ''
        return (getattr(profile, 'contact_email', None) or '').strip()
    return (getattr(user, 'email', None) or '').strip()


def _unique_guest_patient_id() -> str:
    """Return a short unique patient_id like G-A1B2C3D4."""
    for _ in range(20):
        candidate = f'G-{uuid.uuid4().hex[:8].upper()}'
        if not PatientProfile.objects.filter(patient_id=candidate).exists():
            return candidate
    return f'G-{uuid.uuid4().hex[:16].upper()}'


def create_guest_user(
    *,
    first_name: str = 'Guest',
    last_name: str = 'Patient',
    phone: str | None = None,
    gender: str | None = None,
    date_of_birth: date | None = None,
    contact_email: str | None = None,
) -> User:
    """
    Create a new patient User + PatientProfile for a staff-registered guest.

    Synthetic login email, unusable password — patient does not log in.
    Optional contact_email is stored on the profile for notifications.
    """
    token = uuid.uuid4().hex
    email = f'guest-{token}@{GUEST_EMAIL_DOMAIN}'
    user = User(
        email=email,
        role=ROLE_PATIENT,
        first_name=(first_name or 'Guest').strip()[:150],
        last_name=(last_name or 'Patient').strip()[:150],
        is_active=True,
    )
    user.set_unusable_password()
    user.save()

    normalized_contact = (contact_email or '').strip()
    profile_defaults: dict = {'patient_id': _unique_guest_patient_id()}
    if phone:
        profile_defaults['phone'] = phone
    if gender:
        profile_defaults['gender'] = gender
    if date_of_birth:
        profile_defaults['date_of_birth'] = date_of_birth
    if normalized_contact:
        profile_defaults['contact_email'] = normalized_contact

    profile, _ = PatientProfile.objects.get_or_create(
        user=user,
        defaults=profile_defaults,
    )
    if not profile.patient_id or profile.patient_id.startswith('TEMP_'):
        profile.patient_id = _unique_guest_patient_id()
        profile.save(update_fields=['patient_id'])

    update_fields: list[str] = []
    if phone and profile.phone != phone:
        profile.phone = phone
        update_fields.append('phone')
    if gender and profile.gender != gender:
        profile.gender = gender
        update_fields.append('gender')
    if date_of_birth and profile.date_of_birth != date_of_birth:
        profile.date_of_birth = date_of_birth
        update_fields.append('date_of_birth')
    if normalized_contact and profile.contact_email != normalized_contact:
        profile.contact_email = normalized_contact
        update_fields.append('contact_email')
    if update_fields:
        profile.save(update_fields=update_fields)

    user.patient_profile = profile
    return user


def find_guest_by_contact_email(contact_email: str) -> User | None:
    """Return an existing guest user whose profile contact_email matches (case-insensitive)."""
    from django.db.models import Q

    normalized = (contact_email or '').strip()
    if not normalized:
        return None
    profile = (
        PatientProfile.objects.filter(contact_email__iexact=normalized)
        .filter(
            Q(user__email__iendswith=f'@{GUEST_EMAIL_DOMAIN}')
            | Q(user__email__iendswith=f'@{LEGACY_GUEST_EMAIL_DOMAIN}')
        )
        .select_related('user')
        .first()
    )
    return profile.user if profile else None


def get_or_create_guest_for_invite(
    *,
    first_name: str,
    last_name: str,
    contact_email: str,
    phone: str | None = None,
) -> tuple[User, bool]:
    """
    Reuse an existing guest by contact email, or create a new guest account.
    Returns (user, created).
    """
    existing = find_guest_by_contact_email(contact_email)
    if existing:
        update_fields: list[str] = []
        fn = (first_name or '').strip()[:150]
        ln = (last_name or '').strip()[:150]
        if fn and existing.first_name != fn:
            existing.first_name = fn
            update_fields.append('first_name')
        if ln and existing.last_name != ln:
            existing.last_name = ln
            update_fields.append('last_name')
        if update_fields:
            existing.save(update_fields=update_fields)
        profile = getattr(existing, 'patient_profile', None)
        if profile and phone and profile.phone != phone:
            profile.phone = phone
            profile.save(update_fields=['phone'])
        return existing, False
    return create_guest_user(
        first_name=first_name,
        last_name=last_name,
        contact_email=contact_email,
        phone=phone,
    ), True
