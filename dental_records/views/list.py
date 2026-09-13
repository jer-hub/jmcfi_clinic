"""Dental record list view and list-building helpers."""

from datetime import datetime
from urllib.parse import urlparse

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import models
from django.http import QueryDict
from django.shortcuts import render
from django.test import RequestFactory
from django.urls import reverse
from django.utils import timezone

from appointments.models import Appointment
from core.decorators import role_required
from core.htmx_utils import is_htmx_request
from core.roles import is_patient_role
from dental_records.models import DentalRecord


def _is_missed_pending_appointment(appointment) -> bool:
    """True if appointment is missed or still pending after its scheduled slot."""
    if not appointment:
        return False
    if appointment.status == 'missed':
        return True
    if appointment.status != 'pending':
        return False
    now = timezone.localtime()
    if appointment.date < now.date():
        return True
    if appointment.date == now.date() and appointment.time < now.time():
        return True
    return False


def _effective_dental_list_get_params(request):
    for header_name in ('HX-Current-URL', 'Referer'):
        raw = (request.headers.get(header_name) or '').strip()
        if raw:
            q = urlparse(raw).query
            if q:
                return QueryDict(q)
    return request.GET


def _dental_list_request_for_params(original_request, get_params: QueryDict):
    rf = RequestFactory()
    path = reverse('dental_records:dental_record_list')
    list_req = rf.get(
        path,
        data=get_params.dict(),
        HTTP_HOST=original_request.get_host(),
        secure=original_request.is_secure(),
    )
    list_req.user = original_request.user
    return list_req


_DENTAL_LIST_STATUS_KEYS = ('pending', 'missed', 'completed', 'cancelled')
_DENTAL_LIST_PAGE_SIZE = 10


def _dental_patient_search_q(field_prefix: str, search_query: str) -> models.Q:
    return (
        models.Q(**{f'{field_prefix}__first_name__icontains': search_query})
        | models.Q(**{f'{field_prefix}__last_name__icontains': search_query})
        | models.Q(**{f'{field_prefix}__email__icontains': search_query})
        | models.Q(**{f'{field_prefix}__patient_profile__patient_id__icontains': search_query})
    )


def _effective_dental_row_status(row) -> str:
    if row.get('missed_slot'):
        return 'missed'
    if row['row_type'] == 'record':
        record = row['record']
        appt = record.appointment if record.appointment_id else None
        if appt and appt.status == 'cancelled':
            return 'cancelled'
        return record.status
    appointment = row['appointment']
    if appointment.status == 'cancelled':
        return 'cancelled'
    return 'pending'


def _dental_list_stat_filter_url(get_params: QueryDict, status_key: str) -> str:
    q = get_params.copy()
    current = (q.get('status') or '').strip()
    if current == status_key:
        q.pop('status', None)
    else:
        q['status'] = status_key
    q.pop('page', None)
    base = reverse('dental_records:dental_record_list')
    encoded = q.urlencode()
    return f'{base}?{encoded}' if encoded else base


def _dental_list_stat_filter_urls(get_params: QueryDict) -> dict[str, str]:
    return {key: _dental_list_stat_filter_url(get_params, key) for key in _DENTAL_LIST_STATUS_KEYS}


def _dental_list_querystring(get_params: QueryDict) -> str:
    q = get_params.copy()
    q.pop('page', None)
    encoded = q.urlencode()
    return f'&{encoded}' if encoded else ''


def _build_unpaginated_dental_table_data(request_user, get_params: QueryDict):
    """
    Same filtered timeline as dental_record_list, unpaginated.
    Returns dict with table_rows, status_totals, search_query, date_from, date_to.
    """
    if is_patient_role(request_user.role):
        dental_records = DentalRecord.objects.filter(
            patient=request_user
        ).select_related('patient', 'examined_by', 'appointment')
    else:
        dental_records = DentalRecord.objects.select_related('patient', 'examined_by', 'appointment').all()

    search_query = (get_params.get('search') or '').strip()
    if search_query:
        dental_records = dental_records.filter(_dental_patient_search_q('patient', search_query))

    date_from = get_params.get('date_from')
    date_to = get_params.get('date_to')
    if date_from:
        dental_records = dental_records.filter(date_of_examination__gte=date_from)
    if date_to:
        dental_records = dental_records.filter(date_of_examination__lte=date_to)

    pending_dental_appointments = Appointment.objects.filter(
        appointment_type='dental',
        status__in=['pending', 'cancelled'],
    ).exclude(
        dental_records__isnull=False,
    ).select_related('patient', 'doctor').distinct()

    if is_patient_role(request_user.role):
        pending_dental_appointments = pending_dental_appointments.filter(patient=request_user)

    if search_query:
        pending_dental_appointments = pending_dental_appointments.filter(
            _dental_patient_search_q('patient', search_query)
        )

    if date_from:
        pending_dental_appointments = pending_dental_appointments.filter(date__gte=date_from)
    if date_to:
        pending_dental_appointments = pending_dental_appointments.filter(date__lte=date_to)

    status_filter = (get_params.get('status') or '').strip()
    status_totals = {key: 0 for key in _DENTAL_LIST_STATUS_KEYS}
    table_rows = []

    for record in dental_records:
        if record.appointment and record.appointment.time:
            row_time = record.appointment.time
        else:
            row_time = record.created_at.time()

        missed_slot = bool(record.appointment_id) and _is_missed_pending_appointment(record.appointment)

        table_rows.append({
            'row_type': 'record',
            'record': record,
            'sort_datetime': datetime.combine(record.date_of_examination, row_time),
            'missed_slot': missed_slot,
        })

    for appointment in pending_dental_appointments:
        missed_slot = appointment.status == 'pending' and _is_missed_pending_appointment(appointment)

        table_rows.append({
            'row_type': 'appointment',
            'appointment': appointment,
            'sort_datetime': datetime.combine(appointment.date, appointment.time),
            'missed_slot': missed_slot,
        })

    table_rows.sort(key=lambda row: row['sort_datetime'], reverse=True)

    for row in table_rows:
        row_status = _effective_dental_row_status(row)
        if row_status in status_totals:
            status_totals[row_status] += 1

    if status_filter in _DENTAL_LIST_STATUS_KEYS:
        table_rows = [
            row for row in table_rows
            if _effective_dental_row_status(row) == status_filter
        ]

    return {
        'table_rows': table_rows,
        'status_totals': status_totals,
        'search_query': search_query,
        'date_from': date_from or '',
        'date_to': date_to or '',
        'status': status_filter,
    }


def _build_dental_list_page_context(request, *, get_params=None):
    if get_params is None:
        get_params = request.GET
    data = _build_unpaginated_dental_table_data(request.user, get_params)
    list_req = _dental_list_request_for_params(request, get_params)
    page_obj = Paginator(data['table_rows'], _DENTAL_LIST_PAGE_SIZE).get_page(
        list_req.GET.get('page')
    )
    list_status = (get_params.get('status') or '').strip()
    return {
        'page_obj': page_obj,
        'total_count': page_obj.paginator.count,
        'status_totals': data['status_totals'],
        'search_query': data['search_query'],
        'date_from': data['date_from'] or None,
        'date_to': data['date_to'] or None,
        'list_status': list_status,
        'dr_filter_urls': _dental_list_stat_filter_urls(get_params),
        'dr_stat_active': {key: list_status == key for key in _DENTAL_LIST_STATUS_KEYS},
        'dr_list_querystring': _dental_list_querystring(get_params),
    }


@login_required
@role_required('student', 'staff', 'doctor')
def dental_record_list(request):
    """List all dental records with search and filtering"""
    context = _build_dental_list_page_context(request)
    if is_htmx_request(request):
        return render(request, 'dental_records/_dr_list_filter_oob.html', context)
    return render(request, 'dental_records/dental_record_list.html', context)
