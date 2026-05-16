"""Document request service layer."""

from .certificates import build_certificate_form_initial, save_certificate_draft
from .errors import (
    CertificateIncompleteError,
    DocumentRequestServiceError,
    InvalidTransitionError,
    MissingCertificateError,
    PdfGenerationError,
    RejectionReasonRequiredError,
    SignatureRequiredError,
)
from .pdf import generate_and_store_certificate_pdf, get_or_create_certificate_pdf_bytes, resolve_wkhtmltopdf_path
from .policies import (
    ALLOWED_DOCUMENT_TYPES,
    LIST_PAGE_SIZE,
    signature_required_for_processor,
    user_can_initiate_on_behalf,
    user_can_process_documents,
)
from .requests import (
    approve_request,
    complete_document_request,
    create_document_request,
    reject_document_request,
    reject_request,
)
from .selectors import (
    apply_list_filters,
    get_assigned_doctors_for_student,
    get_certificate_signature_display,
    get_clinician_signature,
    get_document_request_for_detail,
    get_document_requests_queryset,
    get_status_totals,
)
from .signatures import apply_signature_to_certificate, mark_certificate_reviewed

__all__ = [
    'ALLOWED_DOCUMENT_TYPES',
    'LIST_PAGE_SIZE',
    'CertificateIncompleteError',
    'DocumentRequestServiceError',
    'InvalidTransitionError',
    'MissingCertificateError',
    'PdfGenerationError',
    'RejectionReasonRequiredError',
    'SignatureRequiredError',
    'apply_list_filters',
    'apply_signature_to_certificate',
    'approve_request',
    'build_certificate_form_initial',
    'complete_document_request',
    'create_document_request',
    'generate_and_store_certificate_pdf',
    'get_assigned_doctors_for_student',
    'get_certificate_signature_display',
    'get_clinician_signature',
    'get_document_request_for_detail',
    'get_document_requests_queryset',
    'get_or_create_certificate_pdf_bytes',
    'get_status_totals',
    'mark_certificate_reviewed',
    'reject_document_request',
    'reject_request',
    'resolve_wkhtmltopdf_path',
    'save_certificate_draft',
    'signature_required_for_processor',
    'user_can_initiate_on_behalf',
    'user_can_process_documents',
]
