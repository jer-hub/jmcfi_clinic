"""Canonical user roles and legacy aliases for the student → patient rename."""

from __future__ import annotations

ROLE_ADMIN = 'admin'
ROLE_DOCTOR = 'doctor'
ROLE_STAFF = 'staff'
ROLE_PATIENT = 'patient'

# Deprecated stored value; normalized to patient everywhere.
LEGACY_ROLE_STUDENT = 'student'

ALL_ROLES: tuple[str, ...] = (ROLE_ADMIN, ROLE_DOCTOR, ROLE_STAFF, ROLE_PATIENT)

ROLE_LABELS: dict[str, str] = {
    ROLE_ADMIN: 'Admin',
    ROLE_DOCTOR: 'Doctor',
    ROLE_STAFF: 'Staff',
    ROLE_PATIENT: 'Patient',
}


def normalize_role(role: str | None) -> str:
    """Map legacy student role to patient."""
    if not role:
        return ROLE_PATIENT
    if role == LEGACY_ROLE_STUDENT:
        return ROLE_PATIENT
    return role


def expand_roles(*roles: str) -> frozenset[str]:
    """Expand role_required tuples so legacy 'student' matches patient users."""
    expanded: set[str] = set()
    for role in roles:
        if role in (LEGACY_ROLE_STUDENT, ROLE_PATIENT):
            expanded.add(ROLE_PATIENT)
        else:
            expanded.add(role)
    return frozenset(expanded)


def role_matches(user_role: str | None, *allowed: str) -> bool:
    return normalize_role(user_role) in expand_roles(*allowed)


# Stored role values that map to the patient role (for ORM filters).
PATIENT_ROLE_VALUES: tuple[str, ...] = (ROLE_PATIENT, LEGACY_ROLE_STUDENT)


def is_patient_role(role: str | None) -> bool:
    return normalize_role(role) == ROLE_PATIENT


def filter_users_by_role(queryset, role_filter: str | None):
    """Filter a User queryset by role, expanding patient/student aliases."""
    if not role_filter:
        return queryset
    if role_filter in PATIENT_ROLE_VALUES:
        return queryset.filter(role__in=PATIENT_ROLE_VALUES)
    return queryset.filter(role=role_filter)
