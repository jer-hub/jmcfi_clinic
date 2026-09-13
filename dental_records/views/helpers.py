"""Shared private helpers for dental record views."""

from django.utils import timezone

from core.clinical_audit import log_clinical_access, _dental_record_label
from core.guest_auth import is_guest_user, resolve_patient_contact_email
from core.list_utils import _is_json_request as _is_json_request

from dental_records.models import (
    DentalExamination,
    DentalHistory,
    DentalHealthQuestionnaire,
    DentalRecord,
    DentalSystemsReview,
    DentalVitalSigns,
)

__all__ = [
    '_audit_dental',
    '_create_dental_clinical_shells',
    '_create_guest_dental_intake_draft',
    '_dental_action_bar_context',
    '_is_json_request',
]


def _audit_dental(request, record, action, **metadata):
    log_clinical_access(
        request,
        action=action,
        resource_type='dental_record',
        resource_id=record.id,
        patient=record.patient,
        resource_label=_dental_record_label(record),
        metadata=metadata or None,
    )


def _dental_action_bar_context(dental_record):
    """Shared context for edit-page status/action bar partials."""
    return {
        'dental_record': dental_record,
        'can_resend_guest_intake': (
            is_guest_user(dental_record.patient)
            and dental_record.intake_status == 'awaiting_guest'
        ),
    }


def _create_dental_clinical_shells(dental_record):
    """Create empty related clinical sections for a new dental record draft."""
    DentalExamination.objects.create(dental_record=dental_record)
    DentalVitalSigns.objects.create(dental_record=dental_record)
    DentalHealthQuestionnaire.objects.create(dental_record=dental_record)
    DentalSystemsReview.objects.create(dental_record=dental_record)
    DentalHistory.objects.create(dental_record=dental_record)


def _create_guest_dental_intake_draft(*, patient, examined_by, appointment=None):
    """Create a pending dental record awaiting guest demographics/consent."""
    contact = resolve_patient_contact_email(patient) or ''
    dental_record = DentalRecord(
        patient=patient,
        examined_by=examined_by,
        appointment=appointment,
        status='pending',
        intake_status='awaiting_guest',
        designation='student',
        department_college_office='Guest',
        course='',
        year_level='',
        email=contact,
        date_of_examination=timezone.now().date(),
    )
    dental_record.save()
    _create_dental_clinical_shells(dental_record)
    return dental_record
