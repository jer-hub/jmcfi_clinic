from django.contrib.auth import get_user_model

from appointments.models import Appointment
from document_request.models import DocumentRequest as CertificateRequest
from medical_records.models import MedicalRecord

from .models import AccountProvisioningAudit
from .utils import get_user_profile

User = get_user_model()


def _get_client_ip(request):
    forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if forwarded_for:
        return forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', 'unknown')


def get_user_management_stats():
    return {
        'total_users': User.objects.count(),
        'total_appointments': Appointment.objects.count(),
        'pending_certificates': CertificateRequest.objects.filter(status='pending').count(),
        'active_doctors': User.objects.filter(role='doctor').count(),
        'total_students': User.objects.filter(role='student').count(),
        'total_staff': User.objects.filter(role__in=['staff', 'doctor']).count(),
        'total_admins': User.objects.filter(role='admin').count(),
        'active_users': User.objects.filter(is_active=True).count(),
        'inactive_users': User.objects.filter(is_active=False).count(),
    }


def get_user_detail_summary(user):
    profile = get_user_profile(user)

    if user.role == 'student':
        stats = {
            'Total Appointments': Appointment.objects.filter(student=user).count(),
            'Completed Appointments': Appointment.objects.filter(student=user, status='completed').count(),
            'Pending Appointments': Appointment.objects.filter(student=user, status='pending').count(),
            'Medical Records': MedicalRecord.objects.filter(student=user).count(),
            'Certificate Requests': CertificateRequest.objects.filter(student=user).count(),
        }
        recent_activity = {
            'appointments': Appointment.objects.filter(student=user).order_by('-created_at')[:5],
            'medical_records': MedicalRecord.objects.filter(student=user).order_by('-created_at')[:5],
        }
    elif user.role in {'staff', 'doctor'}:
        stats = {
            'Total Appointments': Appointment.objects.filter(doctor=user).count(),
            'Completed Appointments': Appointment.objects.filter(doctor=user, status='completed').count(),
            'Pending Appointments': Appointment.objects.filter(doctor=user, status='pending').count(),
            'Medical Records': MedicalRecord.objects.filter(doctor=user).count(),
            'Certificates Processed': CertificateRequest.objects.filter(processed_by=user).count(),
        }
        recent_activity = {
            'appointments': Appointment.objects.filter(doctor=user).order_by('-created_at')[:5],
            'medical_records': MedicalRecord.objects.filter(doctor=user).order_by('-created_at')[:5],
        }
    elif user.role == 'admin':
        audits = AccountProvisioningAudit.objects.filter(actor=user).select_related('target_user').order_by('-created_at')
        stats = {
            'Provisioning Actions': audits.count(),
            'Users Touched': audits.values('target_user').distinct().count(),
            'Active Users': User.objects.filter(is_active=True).count(),
            'Pending Activations': User.objects.filter(onboarding_status=User.ONBOARDING_STATUS.PENDING_ACTIVATION).count(),
        }
        recent_activity = {
            'audit_logs': audits[:5],
        }
    else:
        stats = {}
        recent_activity = {}

    return profile, stats, recent_activity


def soft_delete_user(*, request, actor, target_user):
    was_active = target_user.is_active
    target_user.soft_delete()

    AccountProvisioningAudit.objects.create(
        actor=actor,
        target_user=target_user,
        action=AccountProvisioningAudit.ACTION.SOFT_DELETED,
        ip_address=_get_client_ip(request),
        metadata={
            'triggered_by': 'single_action',
            'was_active': was_active,
        },
    )


def restore_user(*, request, actor, target_user):
    target_user.restore()

    AccountProvisioningAudit.objects.create(
        actor=actor,
        target_user=target_user,
        action=AccountProvisioningAudit.ACTION.RESTORED,
        ip_address=_get_client_ip(request),
        metadata={
            'triggered_by': 'single_action',
        },
    )


def toggle_user_status(*, request, actor, target_user):
    was_pending = target_user.onboarding_status == User.ONBOARDING_STATUS.PENDING_ACTIVATION
    target_user.is_active = not target_user.is_active
    target_user.onboarding_status = (
        User.ONBOARDING_STATUS.ACTIVE if target_user.is_active else User.ONBOARDING_STATUS.SUSPENDED
    )
    target_user.save()

    AccountProvisioningAudit.objects.create(
        actor=actor,
        target_user=target_user,
        action=(
            AccountProvisioningAudit.ACTION.ACTIVATED
            if target_user.is_active
            else AccountProvisioningAudit.ACTION.SUSPENDED
        ),
        ip_address=_get_client_ip(request),
        metadata={
            'triggered_by': 'single_action',
            'was_pending': was_pending,
            'onboarding_status': target_user.onboarding_status,
            'is_active': target_user.is_active,
        },
    )

    return was_pending