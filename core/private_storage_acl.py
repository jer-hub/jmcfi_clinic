"""Authorization for private storage proxy paths."""

from __future__ import annotations

from core.doctor_access import MODULE_FILES, has_clinical_module
from core.roles import ROLE_ADMIN, ROLE_DOCTOR, ROLE_STAFF, is_patient_role, normalize_role


def _is_clinic_staff(user) -> bool:
    return normalize_role(getattr(user, 'role', None)) in {
        ROLE_ADMIN,
        ROLE_DOCTOR,
        ROLE_STAFF,
    }


def _can_access_profile_image(user, path: str) -> bool:
    from core.models import PatientProfile, StaffProfile

    if path.startswith('profiles/patients/') or path.startswith('profiles/students/'):
        profile = PatientProfile.objects.filter(profile_image=path).select_related('user').first()
        if profile is None:
            return False
        if _is_clinic_staff(user):
            return True
        return profile.user_id == user.id

    if path.startswith('profiles/staff/'):
        profile = StaffProfile.objects.filter(profile_image=path).select_related('user').first()
        if profile is None:
            return False
        if _is_clinic_staff(user):
            return True
        return profile.user_id == user.id

    return False


def _can_access_certificate_path(user, path: str) -> bool:
    from document_request.models import MedicalCertificate
    from document_request.services.policies import InvalidTransitionError, assert_can_download_pdf

    if path.startswith('certificates/issued/'):
        certificate = (
            MedicalCertificate.objects.filter(issued_pdf=path)
            .select_related('document_request', 'user')
            .first()
        )
        if certificate is None:
            return False
        if is_patient_role(user.role) and certificate.user_id != user.id:
            return False
        if not _is_clinic_staff(user) and not is_patient_role(user.role):
            return False
        try:
            assert_can_download_pdf(certificate.document_request, certificate)
        except InvalidTransitionError:
            return False
        return True

    if path.startswith('signatures/certificate_snapshots/'):
        certificate = (
            MedicalCertificate.objects.filter(signature_snapshot=path)
            .select_related('user')
            .first()
        )
        if certificate is None:
            return False
        if is_patient_role(user.role):
            return certificate.user_id == user.id
        return _is_clinic_staff(user)

    if path.startswith('signatures/doctors/'):
        from document_request.models import ClinicianSignature

        if not _is_clinic_staff(user):
            return False
        return ClinicianSignature.objects.filter(signature_image=path).exists()

    return False


def _can_access_drive_path(user, path: str) -> bool:
    from files.models import DriveItem

    role = normalize_role(getattr(user, 'role', None))
    if role not in {ROLE_STAFF, ROLE_DOCTOR}:
        return False
    if not has_clinical_module(user, MODULE_FILES):
        return False
    return DriveItem.objects.filter(file=path, kind=DriveItem.Kind.FILE).exists()


def can_access_private_path(user, path: str) -> bool:
    """
    Return True if authenticated user may stream the given storage key.

    Unknown prefixes are denied. Missing model rows for object-backed paths are denied.
    """
    if not user or not getattr(user, 'is_authenticated', False):
        return False

    path = (path or '').strip().lstrip('/')
    if not path or '..' in path.split('/'):
        return False

    if path.startswith('clinic/') or path.startswith('health_tips/'):
        return True

    if path.startswith('profiles/'):
        return _can_access_profile_image(user, path)

    if path.startswith('signatures/') or path.startswith('certificates/'):
        return _can_access_certificate_path(user, path)

    if path.startswith('drive/'):
        return _can_access_drive_path(user, path)

    return False
