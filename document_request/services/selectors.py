"""Read-only query helpers for document requests."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db.models import Q, QuerySet

from appointments.models import Appointment, AppointmentTypeDefault
from core.roles import PATIENT_ROLE_VALUES, is_patient_role
from core.utils import patient_search_q

from document_request.models import ClinicianSignature, DocumentRequest, MedicalCertificate

from .policies import PROCESSOR_ROLES

User = get_user_model()


def get_document_requests_queryset(user) -> QuerySet:
    """Role-scoped base queryset for list views."""
    qs = DocumentRequest.objects.select_related(
        'patient',
        'medical_certificate',
        'processed_by',
        'created_by',
        'assigned_to',
    )
    role = getattr(user, 'role', None)
    if is_patient_role(role):
        return qs.filter(patient=user)
    if role in PROCESSOR_ROLES:
        return qs.all()
    return qs.none()


def apply_list_filters(
    queryset: QuerySet,
    *,
    status: str | None = None,
    document_type: str | None = None,
    date_from=None,
    date_to=None,
    search: str | None = None,
) -> QuerySet:
    qs = queryset
    if document_type:
        qs = qs.filter(document_type=document_type)
    if date_from:
        qs = qs.filter(created_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(created_at__date__lte=date_to)
    if status:
        qs = qs.filter(status=status)
    search = (search or '').strip()
    if search:
        matching_patients = User.objects.filter(role__in=PATIENT_ROLE_VALUES).filter(patient_search_q(search))
        qs = qs.filter(
            Q(purpose__icontains=search)
            | Q(patient__in=matching_patients)
        )
    return qs.order_by('-created_at')


def get_status_totals(queryset: QuerySet) -> dict[str, int]:
    return {
        DocumentRequest.Status.PENDING_REVIEW: queryset.filter(
            status=DocumentRequest.Status.PENDING_REVIEW
        ).count(),
        DocumentRequest.Status.COMPLETED: queryset.filter(
            status=DocumentRequest.Status.COMPLETED
        ).count(),
        DocumentRequest.Status.REJECTED: queryset.filter(
            status=DocumentRequest.Status.REJECTED
        ).count(),
    }


def get_assigned_doctors_for_student(student) -> list:
    """
    Resolve clinician(s) who should receive a new certificate request notification.

    Priority:
    1. Doctor on the student's most recent non-cancelled appointment
    2. Doctors assigned to the active consultation appointment type default
    """
    appt = (
        Appointment.objects.filter(patient=student)
        .exclude(status='cancelled')
        .select_related('doctor')
        .order_by('-date', '-time')
        .first()
    )
    if appt and appt.doctor_id and appt.doctor.is_active and appt.doctor.role in ('doctor', 'staff'):
        return [appt.doctor]

    type_default = (
        AppointmentTypeDefault.objects.filter(appointment_type='consultation', is_active=True)
        .prefetch_related('assigned_doctors')
        .first()
    )
    if type_default:
        assigned = list(
            type_default.assigned_doctors.filter(role__in=('doctor', 'staff'), is_active=True).order_by(
                'last_name', 'first_name'
            )
        )
        if assigned:
            return assigned

    return []


def get_clinician_signature(user) -> ClinicianSignature | None:
    if getattr(user, 'role', None) not in ('doctor', 'staff', 'admin'):
        return None
    return ClinicianSignature.objects.filter(doctor=user, is_active=True).first()


def get_certificate_signature_display(certificate: MedicalCertificate) -> ClinicianSignature | None:
    """Signature for preview/PDF — signing clinician or immutable snapshot."""
    if certificate.signed_by_id:
        sig = ClinicianSignature.objects.filter(doctor_id=certificate.signed_by_id, is_active=True).first()
        if sig and sig.signature_image:
            return sig
    if certificate.reviewed_by_id and certificate.reviewed_by_id != certificate.signed_by_id:
        sig = ClinicianSignature.objects.filter(doctor_id=certificate.reviewed_by_id, is_active=True).first()
        if sig and sig.signature_image:
            return sig
    return None


def get_document_request_for_detail(request_id: int) -> DocumentRequest:
    return DocumentRequest.objects.select_related(
        'patient',
        'medical_certificate',
        'processed_by',
        'created_by',
        'assigned_to',
    ).get(pk=request_id)
