from django.contrib.auth import get_user_model
from django.db.models import Q

from appointments.models import Appointment
from document_request.models import DocumentRequest
from medical_records.models import MedicalRecord

from .models import AccountProvisioningAudit
from .roles import PATIENT_ROLE_VALUES, ROLE_PATIENT, role_matches
from .roles import filter_users_by_role
from .utils import get_user_profile, get_client_ip, paginate_queryset

User = get_user_model()


_get_client_ip = get_client_ip


def get_user_management_stats():
    """Get statistics for the user management page.

    All user counts exclude soft-deleted users (is_deleted=True) for consistency
    with the user list page which filters out deleted users by default.
    """
    return {
        'total_users': User.objects.filter(is_deleted=False).count(),
        'total_appointments': Appointment.objects.count(),
        'pending_certificates': DocumentRequest.objects.filter(
            status=DocumentRequest.Status.PENDING_REVIEW,
        ).count(),
        'active_doctors': User.objects.filter(role='doctor', is_deleted=False).count(),
        'total_patients': User.objects.filter(role__in=PATIENT_ROLE_VALUES, is_deleted=False).count(),
        'total_patients': User.objects.filter(role__in=PATIENT_ROLE_VALUES, is_deleted=False).count(),
        'total_staff': User.objects.filter(role='staff', is_deleted=False).count(),
        'total_admins': User.objects.filter(role='admin', is_deleted=False).count(),
        'active_users': User.objects.filter(is_active=True, is_deleted=False).count(),
        'inactive_users': User.objects.filter(is_active=False, is_deleted=False).count(),
        'pending_activations': User.objects.filter(onboarding_status='pending_activation', is_deleted=False).count(),
        'deleted_users': User.objects.filter(is_deleted=True).count(),
    }


def get_user_detail_summary(user):
    profile = get_user_profile(user)

    if role_matches(user.role, ROLE_PATIENT):
        stats = {
            'Total Appointments': Appointment.objects.filter(patient=user).count(),
            'Completed Appointments': Appointment.objects.filter(patient=user, status='completed').count(),
            'Pending Appointments': Appointment.objects.filter(patient=user, status='pending').count(),
            'Medical Records': MedicalRecord.objects.filter(patient=user).count(),
            'Certificate Requests': DocumentRequest.objects.filter(patient=user).count(),
        }
        recent_activity = {
            'appointments': Appointment.objects.filter(patient=user).order_by('-created_at')[:5],
            'medical_records': MedicalRecord.objects.filter(patient=user).order_by('-created_at')[:5],
        }
    elif user.role in {'staff', 'doctor'}:
        stats = {
            'Total Appointments': Appointment.objects.filter(doctor=user).count(),
            'Completed Appointments': Appointment.objects.filter(doctor=user, status='completed').count(),
            'Pending Appointments': Appointment.objects.filter(doctor=user, status='pending').count(),
            'Medical Records': MedicalRecord.objects.filter(doctor=user).count(),
            'Certificates Processed': DocumentRequest.objects.filter(processed_by=user).count(),
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
            'Active Users': User.objects.filter(is_active=True, is_deleted=False).count(),
            'Pending Activations': User.objects.filter(onboarding_status=User.ONBOARDING_STATUS.PENDING_ACTIVATION, is_deleted=False).count(),
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


def build_active_user_list_context(request):
    """Queryset + filter context for the active user management list (and HTMX partials)."""
    role_filter = request.GET.get('role', '')
    status_filter = request.GET.get('status', '')
    search_query = request.GET.get('search', '')

    users = User.objects.filter(is_deleted=False).order_by('-date_joined')

    if role_filter:
        users = filter_users_by_role(users, role_filter)

    if status_filter == 'active':
        users = users.filter(
            onboarding_status=User.ONBOARDING_STATUS.ACTIVE,
            is_active=True,
        )
    elif status_filter == 'pending':
        users = users.filter(onboarding_status=User.ONBOARDING_STATUS.PENDING_ACTIVATION)
    elif status_filter == 'suspended':
        users = users.filter(onboarding_status=User.ONBOARDING_STATUS.SUSPENDED)
    elif status_filter == 'inactive':
        users = users.filter(is_active=False)

    if search_query:
        users = users.filter(
            Q(username__icontains=search_query)
            | Q(email__icontains=search_query)
            | Q(first_name__icontains=search_query)
            | Q(last_name__icontains=search_query)
        )

    query_copy = request.GET.copy()
    query_copy.pop('page', None)
    user_list_querystring = f'&{query_copy.urlencode()}' if query_copy else ''

    return {
        'users': paginate_queryset(users, request, per_page=20),
        'stats': get_user_management_stats(),
        'role_filter': role_filter,
        'status_filter': status_filter,
        'search_query': search_query,
        'user_list_querystring': user_list_querystring,
        'current_user_id': request.user.pk,
    }