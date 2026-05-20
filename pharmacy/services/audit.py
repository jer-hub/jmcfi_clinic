"""Pharmacy audit trail helpers."""

from __future__ import annotations

from pharmacy.models import AuditLog


def log_action(
    action: str,
    user,
    *,
    medicine=None,
    batch=None,
    quantity: int = 0,
    details: str = '',
) -> AuditLog:
    return AuditLog.objects.create(
        action=action,
        performed_by=user,
        medicine=medicine,
        batch=batch,
        quantity=quantity,
        details=details,
    )
