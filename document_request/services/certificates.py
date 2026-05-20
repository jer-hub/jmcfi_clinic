"""Medical certificate draft editing."""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from document_request.models import MedicalCertificate

from .audit import log_event
from .policies import PROCESSOR_ROLES
from .signatures import mark_certificate_reviewed


CLINICIAN_CREDENTIAL_FIELDS = ('physician_name', 'license_no', 'ptr_no')


def get_clinician_certificate_credentials(user) -> dict[str, str]:
    """Return signing clinician display fields from the authenticated user profile."""
    if getattr(user, 'role', None) not in PROCESSOR_ROLES:
        return {field: '' for field in CLINICIAN_CREDENTIAL_FIELDS}

    from core.models import StaffProfile, User

    user = User.objects.filter(pk=user.pk).first() or user
    staff_profile = None
    try:
        staff_profile = user.staff_profile
    except StaffProfile.DoesNotExist:
        staff_profile = StaffProfile.objects.filter(user_id=user.pk).first()
    lic = ''
    if staff_profile:
        lic = getattr(staff_profile, 'license_number', '') or ''
    lic = lic or getattr(user, 'license_number', '') or getattr(user, 'license_no', '') or ''

    ptr = getattr(user, 'ptr_no', '') or getattr(user, 'ptrno', '') or ''
    if not ptr and staff_profile:
        ptr = getattr(staff_profile, 'ptr_no', '') or getattr(staff_profile, 'ptrno', '') or ''

    return {
        'physician_name': user.get_full_name() or user.email or '',
        'license_no': lic,
        'ptr_no': ptr,
    }


def apply_clinician_credentials(certificate: MedicalCertificate, user) -> None:
    """Stamp certificate with the authenticated clinician's credentials."""
    if getattr(user, 'role', None) not in PROCESSOR_ROLES:
        return
    for field, value in get_clinician_certificate_credentials(user).items():
        setattr(certificate, field, value)


def build_certificate_form_initial(certificate: MedicalCertificate, user) -> dict:
    """Prefill empty certificate fields from student profile and clinician profile."""
    initial: dict = {}
    student = certificate.user
    profile = getattr(student, 'patient_profile', None)
    if profile:
        if not certificate.age and profile.age:
            initial['age'] = profile.age
        if not certificate.gender and profile.gender:
            initial['gender'] = profile.gender
        if not certificate.address and profile.address:
            initial['address'] = profile.address
    if not certificate.patient_name:
        initial['patient_name'] = student.get_full_name() or student.email

    if user.role in PROCESSOR_ROLES:
        initial.update(get_clinician_certificate_credentials(user))

    return initial


@transaction.atomic
def save_certificate_draft(*, certificate: MedicalCertificate, actor, form_cleaned_data: dict) -> MedicalCertificate:
    """Persist certificate edits without issuing or changing request workflow status."""
    for field, value in form_cleaned_data.items():
        setattr(certificate, field, value)
    apply_clinician_credentials(certificate, actor)
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
