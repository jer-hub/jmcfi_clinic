"""Appointment list views and helpers."""

from urllib.parse import urlparse

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, QueryDict
from django.shortcuts import render
from django.template.loader import render_to_string
from django.test import RequestFactory
from django.urls import reverse
from django.db.models import Count, Q
from django.utils.dateparse import parse_date

from appointments.models import Appointment
from core.decorators import role_required
from core.htmx_utils import is_htmx_request, htmx_add_toast, htmx_add_trigger
from core.roles import ROLE_DOCTOR, ROLE_PATIENT, ROLE_STAFF, role_matches

from .helpers import paginate_queryset

User = get_user_model()

_APPOINTMENT_LIST_STATUS_KEYS = ('pending', 'confirmed', 'completed', 'missed', 'cancelled')


def _effective_appointment_list_get_params(request):
    """List filters for HTMX OOB: prefer HX-Current-URL query, then Referer query, then GET."""
    for header_name in ('HX-Current-URL', 'Referer'):
        raw = (request.headers.get(header_name) or '').strip()
        if raw:
            q = urlparse(raw).query
            if q:
                return QueryDict(q)
    return request.GET


def _appointment_list_request_path_matches(url: str) -> bool:
    if not (url or '').strip():
        return False
    list_path = reverse('appointments:appointment_list').rstrip('/')
    path = urlparse(url).path.rstrip('/')
    return path == list_path


def _is_appointment_list_htmx_context(request):
    if _appointment_list_request_path_matches(request.headers.get('HX-Current-URL') or ''):
        return True
    return _appointment_list_request_path_matches(request.headers.get('Referer') or '')


def _appointment_list_request_for_params(original_request, get_params: QueryDict):
    """Build a GET request carrying list filters (pagination + table partial)."""
    rf = RequestFactory()
    path = reverse('appointments:appointment_list')
    list_req = rf.get(
        path,
        data=get_params.dict(),
        HTTP_HOST=original_request.get_host(),
        secure=original_request.is_secure(),
    )
    list_req.user = original_request.user
    return list_req


def _appointment_list_querystring(get_params: QueryDict) -> str:
    q = get_params.copy()
    q.pop('page', None)
    encoded = q.urlencode()
    return f'&{encoded}' if encoded else ''


def _appointment_list_stat_filter_url(get_params: QueryDict, status_key: str) -> str:
    """Toggle *status_key* in list query string; preserve other filters."""
    q = get_params.copy()
    current = (q.get('status') or '').strip()
    if current == status_key:
        q.pop('status', None)
    else:
        q['status'] = status_key
    q.pop('page', None)
    base = reverse('appointments:appointment_list')
    encoded = q.urlencode()
    return f'{base}?{encoded}' if encoded else base


def _appointment_list_stat_filter_urls(get_params: QueryDict) -> dict[str, str]:
    return {key: _appointment_list_stat_filter_url(get_params, key) for key in _APPOINTMENT_LIST_STATUS_KEYS}


def _appointment_list_base_queryset(user):
    if role_matches(user.role, ROLE_PATIENT):
        return Appointment.objects.filter(patient=user)
    if user.role == ROLE_DOCTOR:
        return Appointment.objects.filter(doctor=user)
    if user.role == ROLE_STAFF:
        return Appointment.objects.all()
    if user.role == 'admin':
        return Appointment.objects.all()
    return Appointment.objects.none()


def _apply_appointment_list_filters(queryset, get_params, user, *, apply_status_filter=True):
    status = get_params.get('status')
    date_from_str = get_params.get('date_from')
    date_to_str = get_params.get('date_to')
    doctor_id = get_params.get('doctor')
    appointment_type = get_params.get('appointment_type')
    patient_search = (get_params.get('patient_search') or '').strip()

    if apply_status_filter and status:
        queryset = queryset.filter(status=status)
    if date_from_str:
        date_from = parse_date(date_from_str)
        if date_from:
            queryset = queryset.filter(date__gte=date_from)
    if date_to_str:
        date_to = parse_date(date_to_str)
        if date_to:
            queryset = queryset.filter(date__lte=date_to)
    if doctor_id:
        queryset = queryset.filter(doctor_id=doctor_id)
    if appointment_type:
        queryset = queryset.filter(appointment_type=appointment_type)
    if patient_search and user.role in ['doctor', 'staff']:
        queryset = queryset.filter(
            Q(patient__first_name__icontains=patient_search)
            | Q(patient__last_name__icontains=patient_search)
            | Q(patient__patient_profile__patient_id__icontains=patient_search)
        )

    current_filters = {
        'status': status,
        'date_from': date_from_str,
        'date_to': date_to_str,
        'doctor': int(doctor_id) if doctor_id else None,
        'appointment_type': appointment_type,
        'patient_search': patient_search,
    }
    return queryset, current_filters


def _appointment_list_status_totals(queryset):
    totals = queryset.aggregate(
        pending=Count('id', filter=Q(status='pending')),
        confirmed=Count('id', filter=Q(status='confirmed')),
        completed=Count('id', filter=Q(status='completed')),
        missed=Count('id', filter=Q(status='missed')),
        cancelled=Count('id', filter=Q(status='cancelled')),
    )
    return totals


def _build_appointment_list_context(user, get_params, list_request):
    base_qs = _appointment_list_base_queryset(user)
    qs_for_totals, _ = _apply_appointment_list_filters(
        base_qs, get_params, user, apply_status_filter=False
    )
    status_totals = _appointment_list_status_totals(qs_for_totals)
    appointments_qs, current_filters = _apply_appointment_list_filters(
        base_qs, get_params, user, apply_status_filter=True
    )
    appointments_qs = (
        appointments_qs.select_related('patient', 'doctor', 'patient__patient_profile')
        .prefetch_related('dental_records', 'medicalrecord_set')
        .order_by('-created_at')
    )
    paginated = paginate_queryset(appointments_qs, list_request)
    list_status = (get_params.get('status') or '').strip()
    return {
        'appointments': paginated,
        'total_count': paginated.paginator.count if paginated else 0,
        'status_totals': status_totals,
        'doctors': User.objects.filter(role='doctor').order_by('first_name', 'last_name'),
        'appointment_types': Appointment.APPOINTMENT_TYPE_CHOICES,
        'current_filters': current_filters,
        'appt_list_querystring': _appointment_list_querystring(get_params),
        'appt_filter_urls': _appointment_list_stat_filter_urls(get_params),
        'appt_stat_active': {key: list_status == key for key in _APPOINTMENT_LIST_STATUS_KEYS},
    }


def _appointment_list_htmx_oob_response(request, message, toast_type='success'):
    get_params = _effective_appointment_list_get_params(request)
    list_req = _appointment_list_request_for_params(request, get_params)
    ctx = _build_appointment_list_context(request.user, get_params, list_req)
    oob_html = render_to_string(
        'appointments/_appt_post_status_oob.html',
        {
            'status_totals': ctx['status_totals'],
            'total_count': ctx['total_count'],
            'appt_filter_urls': ctx['appt_filter_urls'],
            'appt_stat_active': ctx['appt_stat_active'],
            'list_table_appointments': ctx['appointments'],
            'list_table_request': list_req,
            'appt_list_querystring': ctx['appt_list_querystring'],
            'user': request.user,
        },
        request=request,
    )
    response = HttpResponse(oob_html, status=200)
    response = htmx_add_trigger(response, 'close-modal')
    return htmx_add_toast(response, message, toast_type)


@login_required
@role_required('student', 'staff', 'doctor')
def appointment_list(request):
    """Display list of appointments based on user role"""
    context = _build_appointment_list_context(request.user, request.GET, request)
    if is_htmx_request(request):
        return render(request, 'appointments/_appt_list_filter_oob.html', context)
    return render(request, 'appointments/appointment_list.html', context)
