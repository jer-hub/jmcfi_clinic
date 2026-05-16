"""Service-layer exceptions for document requests."""


class DocumentRequestServiceError(Exception):
    """Base error with a stable code for view messaging."""

    code = 'error'

    def __init__(self, message: str = ''):
        super().__init__(message)
        self.message = message or self.code


class InvalidTransitionError(DocumentRequestServiceError):
    code = 'invalid_transition'


class SignatureRequiredError(DocumentRequestServiceError):
    code = 'signature_required'


class CertificateIncompleteError(DocumentRequestServiceError):
    code = 'certificate_incomplete'


class MissingCertificateError(DocumentRequestServiceError):
    code = 'missing_certificate'


class RejectionReasonRequiredError(DocumentRequestServiceError):
    code = 'rejection_reason_required'


class PdfGenerationError(DocumentRequestServiceError):
    code = 'pdf_generation_failed'
