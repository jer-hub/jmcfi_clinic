"""Admin views for clinical PHI access audit logs."""

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from .decorators import admin_required
from .models import ClinicalAccessLog, User
from .utils import paginate_queryset


def _filter_clinical_logs(queryset, request):
    """Apply shared query-string filters to a ClinicalAccessLog queryset."""
    action_filter = request.GET.get('action', '').strip()
    resource_type_filter = request.GET.get('resource_type', '').strip()
    patient_q = request.GET.get('patient', '').strip()
    actor_q = request.GET.get('actor', '').strip()
    date_from = request.GET.get('date_from', '').strip()
    date_to = request.GET.get('date_to', '').strip()

    if action_filter:
        queryset = queryset.filter(action=action_filter)
    if resource_type_filter:
        queryset = queryset.filter(resource_type=resource_type_filter)
    if patient_q:
        queryset = queryset.filter(
            Q(patient__first_name__icontains=patient_q)
            | Q(patient__last_name__icontains=patient_q)
            | Q(patient__email__icontains=patient_q)
        )
    if actor_q:
        queryset = queryset.filter(
            Q(actor__first_name__icontains=actor_q)
            | Q(actor__last_name__icontains=actor_q)
            | Q(actor__email__icontains=actor_q)
        )
    if date_from:
        queryset = queryset.filter(created_at__date__gte=date_from)
    if date_to:
        queryset = queryset.filter(created_at__date__lte=date_to)

    return queryset.order_by('-created_at')


def _clinical_log_filter_values(request):
    return {
        'action_filter': request.GET.get('action', '').strip(),
        'resource_type_filter': request.GET.get('resource_type', '').strip(),
        'patient_filter': request.GET.get('patient', '').strip(),
        'actor_filter': request.GET.get('actor', '').strip(),
        'date_from': request.GET.get('date_from', '').strip(),
        'date_to': request.GET.get('date_to', '').strip(),
    }


def _has_active_clinical_filters(filter_values, *, include_patient_filter=True):
    keys = ('action_filter', 'resource_type_filter', 'actor_filter', 'date_from', 'date_to')
    if include_patient_filter:
        keys = ('patient_filter',) + keys
    return any(filter_values.get(key) for key in keys)


def _clinical_log_pagination_querystring(request):
    query = request.GET.copy()
    query.pop('page', None)
    encoded = query.urlencode()
    return f'&{encoded}' if encoded else ''


def _clinical_log_list_context(request, queryset, *, viewed_user=None):
    logs_page = paginate_queryset(queryset, request, per_page=25)
    show_patient = viewed_user is None
    filter_values = _clinical_log_filter_values(request)
    if viewed_user:
        clear_url = reverse('core:patient_clinical_access_log', kwargs={'user_id': viewed_user.pk})
    else:
        clear_url = reverse('core:clinical_access_log')

    return {
        'logs': logs_page,
        'viewed_user': viewed_user,
        'show_patient_column': show_patient,
        'show_patient_filter': show_patient,
        'table_colspan': 7 if show_patient else 6,
        'clear_url': clear_url,
        'has_active_filters': _has_active_clinical_filters(
            filter_values,
            include_patient_filter=show_patient,
        ),
        'pagination_querystring': _clinical_log_pagination_querystring(request),
        'action_choices': ClinicalAccessLog.Action.choices,
        'resource_type_choices': ClinicalAccessLog.ResourceType.choices,
        'settings_subnav_active': 'clinical_audit',
        **filter_values,
    }


@login_required
@admin_required
def clinical_access_log(request):
    """Global clinical access audit log (admin only)."""
    logs = ClinicalAccessLog.objects.select_related('actor', 'patient')
    logs = _filter_clinical_logs(logs, request)
    context = _clinical_log_list_context(request, logs)
    return render(request, 'core/clinical_access_log/list.html', context)


@login_required
@admin_required
def patient_clinical_access_log(request, user_id):
    """Per-patient clinical access audit log (admin only)."""
    user = get_object_or_404(User, id=user_id)
    logs = ClinicalAccessLog.objects.filter(patient=user).select_related('actor', 'patient')
    logs = _filter_clinical_logs(logs, request)
    context = _clinical_log_list_context(request, logs, viewed_user=user)
    return render(request, 'core/clinical_access_log/list.html', context)
