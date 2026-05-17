"""Document request workflow commands."""

from __future__ import annotations

import logging

from django.db import transaction
from django.utils import timezone

from document_request.models import DocumentRequest, DocumentRequestEvent, MedicalCertificate

from .audit import log_event
from .errors import (
    CertificateIncompleteError,
    MissingCertificateError,
    PdfGenerationError,
    RejectionReasonRequiredError,
)

logger = logging.getLogger(__name__)
from .notifications import (
    notify_assigned_clinicians_new_request,
    notify_student_ready,
    notify_student_rejected,
)
from .pdf import generate_and_store_certificate_pdf
from .policies import CLINICAL_INITIATOR_ROLES, assert_can_approve, assert_can_reject
from core.roles import PATIENT_ROLE_VALUES, is_patient_role

from .selectors import get_assigned_doctors_for_student
from .signatures import apply_signature_to_certificate, mark_certificate_reviewed


def _profile_data_from_post(post) -> dict:
    posted_age = post.get('age')
    posted_gender = post.get('gender')
    posted_address = post.get('address')
    if posted_age or posted_gender or posted_address:
        try:
            age_val = int(posted_age) if posted_age else None
        except (TypeError, ValueError):
            age_val = None
        return {
            'age': age_val,
            'gender': posted_gender or '',
            'address': posted_address or '',
        }
    return {}


def _profile_data_from_student(student, post) -> dict:
    data = _profile_data_from_post(post)
    if data:
        return data
    profile = getattr(student, 'patient_profile', None)
    if profile:
        return {
            'age': profile.age,
            'gender': profile.gender,
            'address': profile.address,
        }
    return {}


@transaction.atomic
def create_document_request(*, actor, student, document_type: str, purpose: str, additional_info: str = '', post=None):
    """Create request + linked medical certificate and notify assigned clinician(s)."""
    post = post or {}
    origin = 'patient'
    if actor.role in CLINICAL_INITIATOR_ROLES and not is_patient_role(actor.role):
        origin = 'doctor'

    assigned = get_assigned_doctors_for_student(student)
    assigned_to = assigned[0] if assigned else None

    doc_request = DocumentRequest.objects.create(
        patient=student,
        created_by=actor,
        assigned_to=assigned_to,
        request_origin=origin,
        document_type=document_type,
        purpose=purpose,
        additional_info=additional_info,
        status=DocumentRequest.Status.PENDING_REVIEW,
    )

    if doc_request.requires_medical_certificate:
        profile_data = _profile_data_from_student(student, post)
        physician_name = ''
        if actor.role in ('doctor', 'staff'):
            physician_name = actor.get_full_name() or actor.email or ''

        cert = MedicalCertificate.objects.create(
            document_request=doc_request,
            user=student,
            status=MedicalCertificate.Status.DRAFT,
            certificate_date=timezone.now().date(),
            patient_name=student.get_full_name() or student.email,
            consultation_date=timezone.now().date(),
            diagnosis='',
            physician_name=physician_name,
            remarks_recommendations=additional_info or '',
            **profile_data,
        )
        doc_request.medical_certificate = cert
        doc_request.save(update_fields=['medical_certificate', 'updated_at'])

    log_event(
        request=doc_request,
        actor=actor,
        event_type=DocumentRequestEvent.EventType.CREATED,
    )
    notify_assigned_clinicians_new_request(doc_request, actor)
    return doc_request


@transaction.atomic
def approve_request(doc_request: DocumentRequest, processor) -> DocumentRequest:
    """Approve a pending request: sign certificate, mark completed, cache PDF."""
    assert_can_approve(doc_request)

    if doc_request.requires_medical_certificate:
        cert = doc_request.medical_certificate
        if not cert:
            raise MissingCertificateError('No medical certificate found for this request.')
        if not (cert.diagnosis or '').strip() or not (cert.remarks_recommendations or '').strip():
            raise CertificateIncompleteError(
                'Please fill in diagnosis and remarks before completing.'
            )
        apply_signature_to_certificate(cert, processor)
        cert.status = MedicalCertificate.Status.ISSUED
        cert.save()
        try:
            generate_and_store_certificate_pdf(cert)
        except PdfGenerationError:
            logger.warning(
                'Could not cache issued PDF for certificate %s; approval still recorded.',
                cert.pk,
                exc_info=True,
            )

    doc_request.status = DocumentRequest.Status.COMPLETED
    doc_request.processed_by = processor
    doc_request.save(update_fields=['status', 'processed_by', 'updated_at'])

    log_event(
        request=doc_request,
        actor=processor,
        event_type=DocumentRequestEvent.EventType.APPROVED,
        payload={'certificate_id': doc_request.medical_certificate_id},
    )
    notify_student_ready(doc_request)
    return doc_request


@transaction.atomic
def reject_request(doc_request: DocumentRequest, processor, rejection_reason: str) -> DocumentRequest:
    """Reject a pending request."""
    assert_can_reject(doc_request)

    reason = (rejection_reason or '').strip()
    if not reason:
        raise RejectionReasonRequiredError('Please provide a reason for rejection.')

    doc_request.status = DocumentRequest.Status.REJECTED
    doc_request.rejection_reason = reason
    doc_request.processed_by = processor

    if doc_request.requires_medical_certificate and doc_request.medical_certificate_id:
        cert = doc_request.medical_certificate
        cert.status = MedicalCertificate.Status.VOID
        mark_certificate_reviewed(cert, processor)
        cert.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'updated_at'])

    doc_request.save(update_fields=['status', 'rejection_reason', 'processed_by', 'updated_at'])

    log_event(
        request=doc_request,
        actor=processor,
        event_type=DocumentRequestEvent.EventType.REJECTED,
        payload={'reason': reason},
    )
    notify_student_rejected(doc_request, reason)
    return doc_request


# Backwards-compatible aliases
complete_document_request = approve_request
reject_document_request = reject_request
