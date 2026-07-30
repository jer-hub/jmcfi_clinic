"""Staff-created clinic walk-in (guest) patients — no self-service login."""

from __future__ import annotations

import uuid
from datetime import date

from django.contrib.auth import get_user_model

from .models import PatientProfile
from .roles import ROLE_PATIENT

User = get_user_model()

WALK_IN_EMAIL_DOMAIN = 'walkin.local'
WALK_IN_INSTITUTIONAL_FIELDS = frozenset({'department', 'course', 'year_level'})


def is_walk_in_user(user) -> bool:
    """True for clinic-managed walk-in guests (*@walkin.local)."""
    email = getattr(user, 'email', None) or ''
    return email.lower().endswith(f'@{WALK_IN_EMAIL_DOMAIN}')


def _unique_walk_in_patient_id() -> str:
    """Return a short unique patient_id like WI-A1B2C3D4."""
    for _ in range(20):
        candidate = f'WI-{uuid.uuid4().hex[:8].upper()}'
        if not PatientProfile.objects.filter(patient_id=candidate).exists():
            return candidate
    return f'WI-{uuid.uuid4().hex[:16].upper()}'


def create_walk_in_user(
    *,
    first_name: str = 'Walk-in',
    last_name: str = 'Guest',
    phone: str | None = None,
    gender: str | None = None,
    date_of_birth: date | None = None,
) -> User:
    """
    Create a new patient User + PatientProfile for a staff-registered walk-in guest.

    Synthetic email, unusable password — patient does not log in.
    """
    token = uuid.uuid4().hex
    email = f'walkin-{token}@{WALK_IN_EMAIL_DOMAIN}'
    user = User(
        email=email,
        role=ROLE_PATIENT,
        first_name=(first_name or 'Walk-in').strip()[:150],
        last_name=(last_name or 'Guest').strip()[:150],
        is_active=True,
    )
    user.set_unusable_password()
    user.save()

    profile_defaults: dict = {'patient_id': _unique_walk_in_patient_id()}
    if phone:
        profile_defaults['phone'] = phone
    if gender:
        profile_defaults['gender'] = gender
    if date_of_birth:
        profile_defaults['date_of_birth'] = date_of_birth

    profile, _ = PatientProfile.objects.get_or_create(
        user=user,
        defaults=profile_defaults,
    )
    if not profile.patient_id or profile.patient_id.startswith('TEMP_'):
        profile.patient_id = _unique_walk_in_patient_id()
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
    if update_fields:
        profile.save(update_fields=update_fields)

    user.patient_profile = profile
    return user
