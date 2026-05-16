"""Certificate signing helpers."""

from __future__ import annotations

import hashlib
from pathlib import Path

from django.core.files.base import ContentFile
from django.utils import timezone

from document_request.models import MedicalCertificate

from .errors import SignatureRequiredError
from .policies import signature_required_for_processor
from .selectors import get_clinician_signature


def apply_signature_to_certificate(certificate: MedicalCertificate, processor) -> None:
    if not signature_required_for_processor(processor):
        return

    sig_record = get_clinician_signature(processor)
    if not sig_record or not sig_record.signature_image:
        raise SignatureRequiredError(
            'Upload your signature on the My Signature page before completing a certificate.'
        )

    with sig_record.signature_image.open('rb') as source:
        data = source.read()

    certificate.signature_hash = hashlib.sha256(data).hexdigest()
    certificate.signed_by = processor
    certificate.signed_at = timezone.now()
    certificate.reviewed_by = processor
    certificate.reviewed_at = timezone.now()

    filename = Path(sig_record.signature_image.name).name
    certificate.signature_snapshot.save(filename, ContentFile(data), save=False)


def mark_certificate_reviewed(certificate: MedicalCertificate, reviewer) -> None:
    from .policies import PROCESSOR_ROLES

    if reviewer.role not in PROCESSOR_ROLES:
        return
    certificate.reviewed_by = reviewer
    certificate.reviewed_at = timezone.now()
