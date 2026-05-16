"""Authorization and workflow transition rules."""

from __future__ import annotations

from .errors import InvalidTransitionError

CLINICAL_INITIATOR_ROLES = ('doctor', 'staff', 'admin')
PROCESSOR_ROLES = ('doctor', 'staff', 'admin')
SIGNATURE_REQUIRED_ROLES = ('doctor', 'staff', 'admin')
ALLOWED_DOCUMENT_TYPES = [('medical_certificate', 'Medical Certificate')]
LIST_PAGE_SIZE = 15


def user_can_process_documents(user) -> bool:
    return getattr(user, 'role', None) in PROCESSOR_ROLES


def user_can_initiate_on_behalf(user) -> bool:
    return getattr(user, 'role', None) in CLINICAL_INITIATOR_ROLES


def signature_required_for_processor(user) -> bool:
    return getattr(user, 'role', None) in SIGNATURE_REQUIRED_ROLES


def assert_can_approve(doc_request) -> None:
    from document_request.models import DocumentRequest

    if doc_request.status != DocumentRequest.Status.PENDING_REVIEW:
        raise InvalidTransitionError('Only requests pending review can be approved.')


def assert_can_reject(doc_request) -> None:
    from document_request.models import DocumentRequest

    if doc_request.status != DocumentRequest.Status.PENDING_REVIEW:
        raise InvalidTransitionError('Only requests pending review can be rejected.')


def assert_certificate_accessible(doc_request) -> None:
    """Block viewing or editing a certificate tied to a rejected request."""
    from document_request.models import DocumentRequest

    if doc_request and doc_request.status == DocumentRequest.Status.REJECTED:
        raise InvalidTransitionError(
            'This certificate is not available because the request was rejected.',
        )


def assert_can_download_pdf(doc_request, certificate) -> None:
    from document_request.models import DocumentRequest, MedicalCertificate

    if doc_request and doc_request.status == DocumentRequest.Status.REJECTED:
        raise InvalidTransitionError(
            'Certificate PDF is not available because the request was rejected.',
        )
    if doc_request and doc_request.status != DocumentRequest.Status.COMPLETED:
        raise InvalidTransitionError('Certificate PDF is available after the request is completed.')
    if certificate.status != MedicalCertificate.Status.ISSUED:
        raise InvalidTransitionError('Certificate must be issued before downloading PDF.')
