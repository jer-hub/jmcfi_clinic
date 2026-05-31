"""Clinical PHI access audit trail helpers."""

from __future__ import annotations

import logging

from .models import ClinicalAccessLog
from .utils import get_client_ip

logger = logging.getLogger(__name__)


def _medical_record_label(record) -> str:
    patient_name = record.patient.get_full_name()
    date_str = record.created_at.strftime('%b %d, %Y')
    return f'{patient_name} — {date_str}'


def _dental_record_label(record) -> str:
    patient_name = record.patient.get_full_name()
    if record.date_of_examination:
        date_str = record.date_of_examination.strftime('%b %d, %Y')
        return f'{patient_name} — {date_str}'
    return patient_name


def log_clinical_access(
    request,
    *,
    action: str,
    resource_type: str,
    resource_id: int,
    patient,
    resource_label: str = '',
    metadata: dict | None = None,
) -> ClinicalAccessLog | None:
    """Record a clinical access event. Never raises — failures are logged only."""
    try:
        actor = getattr(request, 'user', None)
        if actor is not None and not getattr(actor, 'is_authenticated', False):
            actor = None
        return ClinicalAccessLog.objects.create(
            actor=actor,
            patient=patient,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            resource_label=resource_label,
            ip_address=get_client_ip(request),
            request_path=getattr(request, 'path', '') or '',
            metadata=metadata or {},
        )
    except Exception:
        logger.exception(
            'Failed to write clinical access log (%s %s:%s)',
            action,
            resource_type,
            resource_id,
        )
        return None
