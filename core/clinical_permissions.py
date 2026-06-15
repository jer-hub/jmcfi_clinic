"""Clinical read/write permission helpers for staff vs doctor roles."""

from __future__ import annotations

from core.roles import ROLE_ADMIN, ROLE_DOCTOR, ROLE_STAFF, normalize_role


def is_staff_clinical_readonly(user) -> bool:
    return normalize_role(getattr(user, 'role', None)) == ROLE_STAFF


def can_write_appointments(user, appointment=None) -> bool:
    role = normalize_role(getattr(user, 'role', None))
    if role == ROLE_STAFF:
        return False
    if role == ROLE_ADMIN:
        return True
    if role == ROLE_DOCTOR:
        if appointment is None:
            return True
        return appointment.doctor_id == user.id
    return False


def can_schedule_for_patient(user) -> bool:
    return normalize_role(getattr(user, 'role', None)) in (ROLE_DOCTOR, ROLE_STAFF, ROLE_ADMIN)


def can_write_medical_records(user) -> bool:
    return normalize_role(getattr(user, 'role', None)) == ROLE_DOCTOR


def can_write_dental_records(user) -> bool:
    return normalize_role(getattr(user, 'role', None)) in (ROLE_DOCTOR, ROLE_ADMIN)
