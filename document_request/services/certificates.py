"""Medical certificate draft editing."""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from document_request.models import MedicalCertificate

from .audit import log_event
from .policies import PROCESSOR_ROLES
from .signatures import mark_certificate_reviewed


def build_certificate_form_initial(certificate: MedicalCertificate, user) -> dict:
    """Prefill empty certificate fields from student profile and clinician profile."""
    initial: dict = {}
    student = certificate.user
    profile = getattr(student, 'student_profile', None)
    if profile:
        if not certificate.age and profile.age:
            initial['age'] = profile.age
        if not certificate.gender and profile.gender:
            initial['gender'] = profile.gender
        if not certificate.address and profile.address:
            initial['address'] = profile.address
    if not certificate.patient_name:
        initial['patient_name'] = student.get_full_name() or student.email

    if user.role not in PROCESSOR_ROLES:
        return initial

    if not certificate.physician_name:
        initial['physician_name'] = user.get_full_name() or user.email or ''

    staff_profile = getattr(user, 'staff_profile', None)
    lic = ''
    if staff_profile:
        lic = getattr(staff_profile, 'license_number', '') or ''
    lic = lic or getattr(user, 'license_number', '') or getattr(user, 'license_no', '') or ''
    if lic and not certificate.license_no:
        initial['license_no'] = lic

    ptr = getattr(user, 'ptr_no', '') or getattr(user, 'ptrno', '') or ''
    if not ptr and staff_profile:
        ptr = getattr(staff_profile, 'ptr_no', '') or getattr(staff_profile, 'ptrno', '') or ''
    if ptr and not certificate.ptr_no:
        initial['ptr_no'] = ptr

    return initial


@transaction.atomic
def save_certificate_draft(*, certificate: MedicalCertificate, actor, form_cleaned_data: dict) -> MedicalCertificate:
    """Persist certificate edits without issuing or changing request workflow status."""
    for field, value in form_cleaned_data.items():
        setattr(certificate, field, value)
    mark_certificate_reviewed(certificate, actor)
    certificate.save()

    from document_request.models import DocumentRequest, DocumentRequestEvent

    doc_request = certificate.document_request
    if doc_request is None:
        doc_request = DocumentRequest.objects.filter(medical_certificate=certificate).first()

    if doc_request:
        log_event(
            request=doc_request,
            actor=actor,
            event_type=DocumentRequestEvent.EventType.CERTIFICATE_SAVED,
            payload={'certificate_id': certificate.pk},
        )
    return certificate
