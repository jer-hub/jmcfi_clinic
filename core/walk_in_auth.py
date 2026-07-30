"""Create and authenticate ephemeral walk-in (guest) patient sessions."""

from __future__ import annotations

import uuid

from django.contrib.auth import get_user_model, login

from .models import PatientProfile
from .roles import ROLE_PATIENT

User = get_user_model()

WALK_IN_EMAIL_DOMAIN = 'walkin.local'
WALK_IN_AUTH_BACKEND = 'django.contrib.auth.backends.ModelBackend'
WALK_IN_INSTITUTIONAL_FIELDS = frozenset({'department', 'course', 'year_level'})


def is_walk_in_user(user) -> bool:
    """True when the user signed in via Continue as Guest (@walkin.local)."""
    email = getattr(user, 'email', None) or ''
    return email.lower().endswith(f'@{WALK_IN_EMAIL_DOMAIN}')


def _unique_walk_in_patient_id() -> str:
    """Return a short unique patient_id like WI-A1B2C3D4."""
    for _ in range(20):
        candidate = f'WI-{uuid.uuid4().hex[:8].upper()}'
        if not PatientProfile.objects.filter(patient_id=candidate).exists():
            return candidate
    return f'WI-{uuid.uuid4().hex[:16].upper()}'


def create_walk_in_user() -> User:
    """
    Create a new patient User + PatientProfile for a walk-in guest session.

    Each call yields a fresh identity (synthetic email, unusable password).
    """
    token = uuid.uuid4().hex
    email = f'walkin-{token}@{WALK_IN_EMAIL_DOMAIN}'
    user = User(
        email=email,
        role=ROLE_PATIENT,
        first_name='Walk-in',
        last_name='Guest',
        is_active=True,
    )
    user.set_unusable_password()
    user.save()

    profile, _ = PatientProfile.objects.get_or_create(
        user=user,
        defaults={'patient_id': _unique_walk_in_patient_id()},
    )
    if not profile.patient_id or profile.patient_id.startswith('TEMP_'):
        profile.patient_id = _unique_walk_in_patient_id()
        profile.save(update_fields=['patient_id'])
    user.patient_profile = profile
    return user


def login_as_walk_in(request) -> User:
    """Create a walk-in user and log them into the request session."""
    user = create_walk_in_user()
    login(request, user, backend=WALK_IN_AUTH_BACKEND)
    return user
