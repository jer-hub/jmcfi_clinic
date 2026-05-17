"""Cached accessors for clinic-wide and per-role runtime settings."""

from __future__ import annotations

from django.conf import settings as django_settings
from django.core.cache import cache

from .profile_policy import (
    ADMIN_PROFILE_REQUIRED_FIELDS,
    DOCTOR_PROFILE_REQUIRED_FIELDS,
    STAFF_PROFILE_REQUIRED_FIELDS,
    STUDENT_PROFILE_REQUIRED_FIELDS,
)

CLINIC_SETTINGS_CACHE_KEY = 'core:clinic_settings'
ROLE_SETTINGS_CACHE_KEY = 'core:role_settings:{role}'
CACHE_TTL = 60

# Session timeouts (seconds) — seeded from legacy SessionTimeoutMiddleware values.
DEFAULT_SESSION_TIMEOUTS = {
    'admin': 43200,
    'doctor': 86400,
    'staff': 86400,
    'student': 86400,
}

ROLE_SETTINGS_DEFAULTS: dict[str, dict] = {
    'admin': {
        'session_timeout_seconds': DEFAULT_SESSION_TIMEOUTS['admin'],
        'profile_required_fields': list(ADMIN_PROFILE_REQUIRED_FIELDS),
        'can_access_analytics': True,
        'can_submit_feedback': False,
        'can_use_messaging': True,
        'can_book_appointments': False,
        'block_clinical_namespaces': True,
        'show_health_tips_nav': False,
    },
    'doctor': {
        'session_timeout_seconds': DEFAULT_SESSION_TIMEOUTS['doctor'],
        'profile_required_fields': list(DOCTOR_PROFILE_REQUIRED_FIELDS),
        'can_access_analytics': True,
        'can_submit_feedback': True,
        'can_use_messaging': True,
        'can_book_appointments': False,
        'block_clinical_namespaces': False,
        'show_health_tips_nav': True,
    },
    'staff': {
        'session_timeout_seconds': DEFAULT_SESSION_TIMEOUTS['staff'],
        'profile_required_fields': list(STAFF_PROFILE_REQUIRED_FIELDS),
        'can_access_analytics': True,
        'can_submit_feedback': True,
        'can_use_messaging': True,
        'can_book_appointments': False,
        'block_clinical_namespaces': False,
        'show_health_tips_nav': False,
    },
    'student': {
        'session_timeout_seconds': DEFAULT_SESSION_TIMEOUTS['student'],
        'profile_required_fields': list(STUDENT_PROFILE_REQUIRED_FIELDS),
        'can_access_analytics': True,
        'can_submit_feedback': True,
        'can_use_messaging': True,
        'can_book_appointments': True,
        'block_clinical_namespaces': False,
        'show_health_tips_nav': True,
    },
}


def invalidate_settings_cache(role: str | None = None) -> None:
    """Clear cached settings after admin updates."""
    cache.delete(CLINIC_SETTINGS_CACHE_KEY)
    if role:
        cache.delete(ROLE_SETTINGS_CACHE_KEY.format(role=role))
        return
    for role_key in ROLE_SETTINGS_DEFAULTS:
        cache.delete(ROLE_SETTINGS_CACHE_KEY.format(role=role_key))


def get_clinic_settings():
    """Return the singleton ClinicSettings instance (cached)."""
    cached = cache.get(CLINIC_SETTINGS_CACHE_KEY)
    if cached is not None:
        return cached

    from .models import ClinicSettings

    obj = ClinicSettings.load()
    cache.set(CLINIC_SETTINGS_CACHE_KEY, obj, CACHE_TTL)
    return obj


def get_role_settings(role: str):
    """Return RoleSettings for the given role (cached, created with defaults if missing)."""
    cached = cache.get(ROLE_SETTINGS_CACHE_KEY.format(role=role))
    if cached is not None:
        return cached

    from .models import RoleSettings

    defaults = ROLE_SETTINGS_DEFAULTS.get(role)
    if defaults is None:
        raise ValueError(f'Unknown role: {role!r}')

    obj, _ = RoleSettings.objects.get_or_create(role=role, defaults=defaults)
    cache.set(ROLE_SETTINGS_CACHE_KEY.format(role=role), obj, CACHE_TTL)
    return obj


def get_effective_session_timeout(user) -> int:
    """Session expiry in seconds for an authenticated user."""
    if user.is_authenticated:
        role = getattr(user, 'role', None)
        if role:
            try:
                return get_role_settings(role).session_timeout_seconds
            except ValueError:
                pass
    clinic = get_clinic_settings()
    return clinic.default_session_hours * 3600


def get_appointment_interval_minutes() -> int:
    """Appointment slot buffer from clinic settings, with Django settings fallback."""
    return get_clinic_settings().appointment_interval_minutes or getattr(
        django_settings,
        'APPOINTMENT_INTERVAL_MINUTES',
        30,
    )


def get_google_allowed_domains() -> list[str]:
    """
    Allowed Google OAuth domains: clinic DB list if set, else env GOOGLE_ALLOWED_DOMAINS.
    """
    from .models import ClinicSettings

    clinic = ClinicSettings.objects.filter(pk=ClinicSettings.SINGLETON_PK).first()
    if clinic:
        raw = (clinic.google_allowed_domains or '').strip()
        if raw:
            return [d.strip().lower() for d in raw.split(',') if d.strip()]
    return list(getattr(django_settings, 'GOOGLE_ALLOWED_DOMAINS', []) or [])


def get_role_features(role: str) -> dict[str, bool]:
    """Feature flags for a role (cached via get_role_settings)."""
    settings = get_role_settings(role)
    return {
        'can_access_analytics': settings.can_access_analytics,
        'can_submit_feedback': settings.can_submit_feedback,
        'can_use_messaging': settings.can_use_messaging,
        'can_book_appointments': settings.can_book_appointments,
        'block_clinical_namespaces': settings.block_clinical_namespaces,
        'show_health_tips_nav': settings.show_health_tips_nav,
    }


def admin_blocks_clinical_namespaces() -> bool:
    """Whether admin users are blocked from clinical app namespaces."""
    try:
        return get_role_settings('admin').block_clinical_namespaces
    except ValueError:
        return True


def get_user_preferences(user):
    """Return preferences for user, creating defaults if needed."""
    from .models import UserPreferences

    prefs, _ = UserPreferences.objects.get_or_create(user=user)
    return prefs


def get_profile_required_fields(role: str) -> list[str]:
    """Required profile fields for a role (DB override with code fallback)."""
    try:
        fields = get_role_settings(role).profile_required_fields
        if fields:
            return list(fields)
    except ValueError:
        pass
    fallback = {
        'student': STUDENT_PROFILE_REQUIRED_FIELDS,
        'staff': STAFF_PROFILE_REQUIRED_FIELDS,
        'doctor': DOCTOR_PROFILE_REQUIRED_FIELDS,
        'admin': ADMIN_PROFILE_REQUIRED_FIELDS,
    }
    return list(fallback.get(role, []))
