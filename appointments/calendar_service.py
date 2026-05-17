"""Dashboard calendar: querysets, event serialization, and month grid building."""

from __future__ import annotations

import calendar as cal_module
from calendar import Calendar
from collections import defaultdict
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from core.roles import ROLE_PATIENT, normalize_role, role_matches
from core.status_styles import (
    APPOINTMENT_STATUS_VARIANTS as STATUS_VARIANTS,
    CALENDAR_FILTER_CHIP_TONES as STATUS_FILTER_CHIP_TONES,
    appointment_status_variant,
)

from .models import Appointment

User = get_user_model()

DEFAULT_STATUSES: tuple[str, ...] = ('pending', 'confirmed', 'completed')
ALL_STATUS_CHOICES: tuple[str, ...] = ('pending', 'confirmed', 'completed', 'cancelled')

WEEKDAY_LABELS: tuple[str, ...] = ('Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat')

STATUS_FILTER_OPTIONS: tuple[dict[str, str], ...] = (
    {'key': 'all', 'label': 'All'},
    {'key': 'pending', 'label': 'Pending'},
    {'key': 'confirmed', 'label': 'Confirmed'},
    {'key': 'completed', 'label': 'Completed'},
    {'key': 'cancelled', 'label': 'Cancelled'},
)

HEAT_LEVEL_CLASSES: tuple[str, ...] = (
    '',  # 0
    'bg-primary-100 text-primary-800 hover:bg-primary-200',
    'bg-primary-300 text-primary-900 hover:bg-primary-400',
    'bg-primary-600 text-white hover:bg-primary-700',
)


VIEW_MODES: tuple[str, ...] = ('month', 'week')


@dataclass
class CalendarFilters:
    year: int
    month: int
    selected_date: date
    doctor_id: int | None = None
    status_filter: str | None = None
    full_page: bool = False
    view_mode: str = 'month'


def parse_doctor_id(raw, user) -> int | None:
    """Staff/admin may filter by doctor; others cannot."""
    if user.role not in ('staff', 'admin'):
        return None
    if not raw:
        return None
    try:
        doctor_id = int(raw)
    except (TypeError, ValueError):
        return None
    if not User.objects.filter(pk=doctor_id, role='doctor').exists():
        return None
    return doctor_id


def parse_view_mode(raw: str | None) -> str:
    value = (raw or 'month').strip().lower()
    if value in VIEW_MODES:
        return value
    return 'month'


def parse_status_filter(raw: str | None) -> str | None:
    if not raw:
        return None
    value = raw.strip().lower()
    if value == 'all':
        return 'all'
    if value in ALL_STATUS_CHOICES:
        return value
    return None


def statuses_for_filter(status_filter: str | None) -> tuple[str, ...]:
    if status_filter == 'all' or status_filter is None:
        return ALL_STATUS_CHOICES
    return (status_filter,)


def get_grid_events_by_date(
    user,
    start: date,
    end: date,
    filters: CalendarFilters,
) -> dict[date, list[dict[str, Any]]]:
    """Events for month/week grids — same status rules as the day panel."""
    statuses = statuses_for_filter(filters.status_filter)
    if filters.status_filter:
        return get_events_by_date(
            user,
            start,
            end,
            statuses=statuses,
            doctor_id=filters.doctor_id,
        )
    return get_combined_events_by_date(
        user,
        start,
        end,
        statuses=statuses,
        doctor_id=filters.doctor_id,
    )


def _grid_day_counts(day_events: list[dict[str, Any]]) -> tuple[int, int, int]:
    """Return (appointment_count, document_count, badge_count) for a grid cell."""
    appt_count = sum(1 for e in day_events if e.get('event_kind') == 'appointment')
    doc_count = sum(1 for e in day_events if e.get('event_kind') == 'document')
    return appt_count, doc_count, appt_count


def parse_calendar_filters(
    get_params,
    user,
    *,
    today: date | None = None,
    full_page: bool = False,
) -> CalendarFilters:
    today = today or timezone.localdate()
    try:
        year = int(get_params.get('year', today.year))
    except (TypeError, ValueError):
        year = today.year
    try:
        month = int(get_params.get('month', today.month))
    except (TypeError, ValueError):
        month = today.month
    month = max(1, min(12, month))
    year = max(1970, min(2100, year))

    from django.utils.dateparse import parse_date

    selected = parse_date(get_params.get('date', '')) or today
    selected = _clamp_selected_date(selected, year, month, today)

    return CalendarFilters(
        year=year,
        month=month,
        selected_date=selected,
        doctor_id=parse_doctor_id(get_params.get('doctor'), user),
        status_filter=parse_status_filter(get_params.get('status')),
        full_page=full_page,
        view_mode=parse_view_mode(get_params.get('view')),
    )


def week_bounds(anchor: date) -> tuple[date, date]:
    """Sunday–Saturday week containing anchor."""
    start = anchor - timedelta(days=(anchor.weekday() + 1) % 7)
    end = start + timedelta(days=6)
    return start, end


def schedule_appointment_url_for_date(d: date) -> str:
    return f"{reverse('appointments:schedule_appointment')}?{urlencode({'date': d.isoformat()})}"


def calendar_queryset(user, *, doctor_id: int | None = None):
    """Role-scoped appointments queryset (staff sees clinic-wide)."""
    qs = Appointment.objects.select_related('patient', 'doctor')
    role = normalize_role(user.role)
    if role == ROLE_PATIENT:
        qs = qs.filter(patient=user)
    elif role == 'doctor':
        qs = qs.filter(doctor=user)
    elif role == 'staff':
        if doctor_id:
            qs = qs.filter(doctor_id=doctor_id)
    elif role == 'admin':
        if doctor_id:
            qs = qs.filter(doctor_id=doctor_id)
    else:
        return Appointment.objects.none()
    return qs


def month_bounds(year: int, month: int) -> tuple[date, date]:
    _, last_day = cal_module.monthrange(year, month)
    return date(year, month, 1), date(year, month, last_day)


def appointment_list_url_for_date(d: date, *, status: str | None = None) -> str:
    params: dict[str, str] = {
        'date_from': d.isoformat(),
        'date_to': d.isoformat(),
    }
    if status:
        params['status'] = status
    return f"{reverse('appointments:appointment_list')}?{urlencode(params)}"


def _format_time(t) -> str:
    return t.strftime('%I:%M %p').lstrip('0')


def serialize_appointment(appt: Appointment, viewer_role: str) -> dict[str, Any]:
    """Serialize one appointment for calendar chips and day agenda."""
    variant = appointment_status_variant(appt.status)
    time_label = _format_time(appt.time)
    detail_url = reverse('appointments:appointment_detail', args=[appt.pk])

    type_label = appt.get_appointment_type_display()
    viewer_role = normalize_role(viewer_role)
    if viewer_role == ROLE_PATIENT:
        chip_label = time_label
        title = type_label
        meta_line = appt.doctor.get_full_name() or appt.doctor.email or 'Doctor'
        meta_prefix = 'Dr.'
    else:
        patient_name = appt.patient.get_full_name() or appt.patient.email or 'Patient'
        chip_label = time_label
        title = patient_name
        meta_line = type_label
        meta_prefix = ''

    return {
        'event_kind': 'appointment',
        'id': appt.pk,
        'date': appt.date,
        'time': appt.time,
        'time_label': time_label,
        'chip_label': chip_label,
        'title': title,
        'meta_line': meta_line,
        'meta_prefix': meta_prefix,
        'status': appt.status,
        'status_label': appt.get_status_display(),
        'variant': variant,
        'appointment_type': appt.appointment_type,
        'appointment_type_label': type_label,
        'detail_url': detail_url,
        'is_cancelled': appt.status == 'cancelled',
        'is_completed': appt.status == 'completed',
        'sort_key': appt.time,
    }


def serialize_document_request(doc_req, viewer_role: str) -> dict[str, Any]:
    """Pending document request for calendar (submitted date)."""
    from document_request.models import DocumentRequest

    submitted = timezone.localtime(doc_req.created_at).date()
    type_label = doc_req.get_document_type_display()
    detail_url = reverse('document_request:document_request_detail', args=[doc_req.pk])

    viewer_role = normalize_role(viewer_role)
    if viewer_role == ROLE_PATIENT:
        title = type_label
        meta_line = 'Pending review'
    else:
        patient_name = doc_req.patient.get_full_name() or doc_req.patient.email or 'Patient'
        title = patient_name
        meta_line = type_label

    return {
        'event_kind': 'document',
        'id': doc_req.pk,
        'date': submitted,
        'time': None,
        'time_label': 'Doc',
        'chip_label': 'Doc',
        'title': title,
        'meta_line': meta_line,
        'meta_prefix': '',
        'status': doc_req.status,
        'status_label': doc_req.get_status_display(),
        'variant': 'info',
        'appointment_type': '',
        'appointment_type_label': type_label,
        'detail_url': detail_url,
        'is_cancelled': False,
        'is_completed': False,
        'sort_key': datetime.min.time(),
    }


def document_requests_queryset(user):
    from document_request.models import DocumentRequest

    qs = DocumentRequest.objects.filter(
        status=DocumentRequest.Status.PENDING_REVIEW,
    ).select_related('patient', 'assigned_to')
    if role_matches(user.role, ROLE_PATIENT):
        return qs.filter(patient=user)
    if user.role in ('doctor', 'staff'):
        return qs
    return DocumentRequest.objects.none()


def get_document_events_by_date(user, start: date, end: date) -> dict[date, list[dict[str, Any]]]:
    """Map submitted-on date to pending document requests."""
    if not role_matches(user.role, ROLE_PATIENT, 'staff', 'doctor'):
        return {}
    by_date: dict[date, list[dict[str, Any]]] = defaultdict(list)
    viewer_role = normalize_role(user.role)
    for doc_req in document_requests_queryset(user):
        submitted = timezone.localtime(doc_req.created_at).date()
        if start <= submitted <= end:
            by_date[submitted].append(serialize_document_request(doc_req, viewer_role))
    return dict(by_date)


def merge_events_by_date(
    appointments: dict[date, list[dict[str, Any]]],
    documents: dict[date, list[dict[str, Any]]],
) -> dict[date, list[dict[str, Any]]]:
    merged: dict[date, list[dict[str, Any]]] = defaultdict(list)
    all_dates = set(appointments) | set(documents)
    for d in all_dates:
        items = appointments.get(d, []) + documents.get(d, [])
        items.sort(key=lambda e: (e.get('sort_key') or datetime.min.time(), e.get('event_kind') != 'appointment'))
        merged[d] = items
    return dict(merged)


def get_combined_events_by_date(
    user,
    start: date,
    end: date,
    *,
    statuses: tuple[str, ...] | None = None,
    doctor_id: int | None = None,
    include_documents: bool = True,
) -> dict[date, list[dict[str, Any]]]:
    appts = get_events_by_date(user, start, end, statuses=statuses, doctor_id=doctor_id)
    if not include_documents:
        return appts
    docs = get_document_events_by_date(user, start, end)
    return merge_events_by_date(appts, docs)


def get_events_by_date(
    user,
    start: date,
    end: date,
    *,
    statuses: tuple[str, ...] | None = None,
    doctor_id: int | None = None,
) -> dict[date, list[dict[str, Any]]]:
    """Map calendar dates to serialized events in range."""
    if statuses is None:
        statuses = DEFAULT_STATUSES
    qs = (
        calendar_queryset(user, doctor_id=doctor_id)
        .filter(date__gte=start, date__lte=end, status__in=statuses)
        .order_by('date', 'time')
    )
    by_date: dict[date, list[dict[str, Any]]] = defaultdict(list)
    for appt in qs:
        by_date[appt.date].append(serialize_appointment(appt, normalize_role(user.role)))
    return dict(by_date)


def get_daily_counts(
    start: date,
    end: date,
    *,
    doctor_id: int | None = None,
    statuses: tuple[str, ...] | None = None,
) -> dict[date, int]:
    """Clinic-wide appointment counts per day (admin heat map)."""
    if statuses is None:
        statuses = DEFAULT_STATUSES
    qs = Appointment.objects.filter(
        date__gte=start,
        date__lte=end,
        status__in=statuses,
    )
    if doctor_id:
        qs = qs.filter(doctor_id=doctor_id)
    from django.db.models import Count

    counts: dict[date, int] = {}
    for row in qs.values('date').annotate(count=Count('id')):
        counts[row['date']] = row['count']
    return counts


def _heat_level(count: int) -> int:
    if count <= 0:
        return 0
    if count <= 2:
        return 1
    if count <= 5:
        return 2
    return 3


def build_month_weeks(year: int, month: int) -> list[list[dict[str, Any]]]:
    """Sunday-start weeks with in-month and weekend flags."""
    cal = Calendar(firstweekday=6)
    weeks: list[list[dict[str, Any]]] = []
    for week in cal.monthdatescalendar(year, month):
        weeks.append([
            {
                'date': d,
                'iso': d.isoformat(),
                'day': d.day,
                'in_month': d.month == month,
                'is_weekend': d.weekday() >= 5,
            }
            for d in week
        ])
    return weeks


def _clamp_selected_date(selected: date | None, year: int, month: int, today: date) -> date:
    if selected is None:
        return today
    start, end = month_bounds(year, month)
    if selected < start:
        return start
    if selected > end:
        return end
    return selected


def _calendar_url_params(filters: CalendarFilters, *, year: int | None = None, month: int | None = None) -> dict[str, str | int]:
    params: dict[str, str | int] = {
        'year': year if year is not None else filters.year,
        'month': month if month is not None else filters.month,
        'date': filters.selected_date.isoformat(),
    }
    if filters.doctor_id:
        params['doctor'] = filters.doctor_id
    if filters.status_filter:
        params['status'] = filters.status_filter
    if filters.full_page:
        params['full'] = '1'
    if filters.view_mode == 'week':
        params['view'] = 'week'
    return params


def _build_calendar_url(route_name: str, params: dict[str, str | int]) -> str:
    return f"{reverse(route_name)}?{urlencode(params)}"


def build_calendar_nav_urls(filters: CalendarFilters) -> dict[str, str]:
    today = timezone.localdate()
    body_route = 'appointments:calendar_body_fragment'
    page_route = 'appointments:appointment_calendar'

    if filters.view_mode == 'week':
        week_start, _ = week_bounds(filters.selected_date)
        prev_anchor = filters.selected_date - timedelta(days=7)
        next_anchor = filters.selected_date + timedelta(days=7)
        today_filters = replace(filters, selected_date=today, year=today.year, month=today.month)

        def week_url(anchor: date) -> str:
            f = replace(filters, selected_date=anchor, year=anchor.year, month=anchor.month)
            return _build_calendar_url(body_route, _calendar_url_params(f))

        nav = {
            'prev': week_url(prev_anchor),
            'next': week_url(next_anchor),
            'today': week_url(today),
        }
        if filters.full_page:
            nav['prev_page'] = _build_calendar_url(page_route, _calendar_url_params(replace(filters, selected_date=prev_anchor)))
            nav['next_page'] = _build_calendar_url(page_route, _calendar_url_params(replace(filters, selected_date=next_anchor)))
            nav['today_page'] = _build_calendar_url(page_route, _calendar_url_params(today_filters))
        return nav

    year, month = filters.year, filters.month
    if month == 1:
        prev_year, prev_month = year - 1, 12
    else:
        prev_year, prev_month = year, month - 1
    if month == 12:
        next_year, next_month = year + 1, 1
    else:
        next_year, next_month = year, month + 1

    def month_url(y: int, m: int) -> str:
        return _build_calendar_url(body_route, _calendar_url_params(filters, year=y, month=m))

    today_filters = replace(
        filters,
        year=today.year,
        month=today.month,
        selected_date=today,
    )
    nav = {
        'prev': month_url(prev_year, prev_month),
        'next': month_url(next_year, next_month),
        'today': _build_calendar_url(body_route, _calendar_url_params(today_filters)),
    }
    if filters.full_page:
        nav['prev_page'] = _build_calendar_url(
            page_route, _calendar_url_params(filters, year=prev_year, month=prev_month)
        )
        nav['next_page'] = _build_calendar_url(
            page_route, _calendar_url_params(filters, year=next_year, month=next_month)
        )
        nav['today_page'] = _build_calendar_url(
            page_route, _calendar_url_params(replace(filters, year=today.year, month=today.month, selected_date=today))
        )
    return nav


def build_calendar_day_url(filters: CalendarFilters, day: date | None = None) -> str:
    params = _calendar_url_params(filters)
    params['date'] = (day or filters.selected_date).isoformat()
    return _build_calendar_url('appointments:calendar_day_fragment', params)


def build_calendar_page_url(filters: CalendarFilters) -> str:
    return _build_calendar_url('appointments:appointment_calendar', _calendar_url_params(filters))


def get_calendar_doctors():
    return User.objects.filter(role='doctor').order_by('first_name', 'last_name')


def build_calendar_filters_context(user, filters: CalendarFilters) -> dict[str, Any]:
    """Doctor filter (staff) and status chips for day panel."""
    status_chips = []
    for opt in STATUS_FILTER_OPTIONS:
        chip_filters = CalendarFilters(
            year=filters.year,
            month=filters.month,
            selected_date=filters.selected_date,
            doctor_id=filters.doctor_id,
            status_filter=opt['key'] or None,
            full_page=filters.full_page,
            view_mode=filters.view_mode,
        )
        inactive_cls, active_cls = STATUS_FILTER_CHIP_TONES.get(
            opt['key'],
            STATUS_FILTER_CHIP_TONES['all'],
        )
        is_active = filters.status_filter == opt['key']
        status_chips.append({
            'key': opt['key'],
            'label': opt['label'],
            'active': is_active,
            'variant': STATUS_VARIANTS.get(opt['key'], 'muted'),
            'chip_class': active_cls if is_active else inactive_cls,
            'url': _build_calendar_url(
                'appointments:calendar_body_fragment',
                _calendar_url_params(chip_filters),
            ),
        })

    def view_url(mode: str) -> str:
        f = replace(filters, view_mode=mode)
        return _build_calendar_url('appointments:calendar_body_fragment', _calendar_url_params(f))

    ctx: dict[str, Any] = {
        'calendar_status_chips': status_chips,
        'calendar_status_filter': filters.status_filter or '',
        'calendar_doctor_id': filters.doctor_id,
        'calendar_show_doctor_filter': user.role == 'staff',
        'calendar_filter_query': urlencode(_calendar_url_params(filters)),
        'calendar_view_mode': filters.view_mode,
        'calendar_view_month_url': view_url('month'),
        'calendar_view_week_url': view_url('week'),
        'calendar_show_week_view': True,
        'calendar_export_ics_url': _build_calendar_url(
            'appointments:calendar_export_ics',
            _calendar_url_params(filters),
        ),
    }
    if user.role == 'staff':
        ctx['calendar_doctors'] = get_calendar_doctors()
    return ctx


def build_calendar_month_context(
    user,
    filters: CalendarFilters,
) -> dict[str, Any]:
    """Context for month grid partial."""
    today = timezone.localdate()
    year, month = filters.year, filters.month
    selected = filters.selected_date
    start, end = month_bounds(year, month)
    events_by_date = get_grid_events_by_date(user, start, end, filters)

    weeks: list[list[dict[str, Any]]] = []
    for week in build_month_weeks(year, month):
        week_cells = []
        for cell in week:
            d = cell['date']
            day_events = events_by_date.get(d, [])
            appt_count, doc_count, badge_count = _grid_day_counts(day_events)
            week_cells.append({
                **cell,
                'is_today': d == today,
                'is_selected': d == selected,
                'events': day_events,
                'event_count': badge_count,
                'document_count': doc_count,
                'visible_events': day_events[:2],
                'overflow_count': max(0, len(day_events) - 2),
                'day_fragment_url': build_calendar_day_url(
                    CalendarFilters(
                        year=year,
                        month=month,
                        selected_date=d,
                        doctor_id=filters.doctor_id,
                        status_filter=filters.status_filter,
                        full_page=filters.full_page,
                        view_mode=filters.view_mode,
                    ),
                    day=d,
                ),
            })
        weeks.append(week_cells)

    month_label = date(year, month, 1).strftime('%B %Y')
    nav = build_calendar_nav_urls(filters)

    return {
        'calendar_weeks': weeks,
        'calendar_year': year,
        'calendar_month': month,
        'calendar_month_label': month_label,
        'calendar_selected_date': selected,
        'calendar_selected_iso': selected.isoformat(),
        'calendar_today_iso': today.isoformat(),
        'calendar_weekday_labels': WEEKDAY_LABELS,
        'calendar_nav_prev_url': nav['prev'],
        'calendar_nav_next_url': nav['next'],
        'calendar_nav_today_url': nav['today'],
        'calendar_nav_prev_page_url': nav.get('prev_page', ''),
        'calendar_nav_next_page_url': nav.get('next_page', ''),
        'calendar_nav_today_page_url': nav.get('today_page', ''),
        'calendar_day_fragment_url': build_calendar_day_url(filters),
        'calendar_viewer_role': normalize_role(user.role),
        'calendar_has_events': bool(events_by_date),
        'calendar_full_page': filters.full_page,
        'calendar_page_url': build_calendar_page_url(filters) if filters.full_page else '',
        'calendar_period_label': month_label,
    }


def build_calendar_week_context(
    user,
    filters: CalendarFilters,
) -> dict[str, Any]:
    """Context for week view (horizontal day strip + day panel)."""
    today = timezone.localdate()
    selected = filters.selected_date
    week_start, week_end = week_bounds(selected)
    events_by_date = get_grid_events_by_date(user, week_start, week_end, filters)

    days: list[dict[str, Any]] = []
    for offset in range(7):
        d = week_start + timedelta(days=offset)
        day_events = events_by_date.get(d, [])
        _appt_count, _doc_count, badge_count = _grid_day_counts(day_events)
        days.append({
            'date': d,
            'iso': d.isoformat(),
            'day': d.day,
            'weekday_label': WEEKDAY_LABELS[offset],
            'is_today': d == today,
            'is_selected': d == selected,
            'is_weekend': d.weekday() >= 5,
            'events': day_events,
            'event_count': badge_count,
            'day_fragment_url': build_calendar_day_url(
                CalendarFilters(
                    year=d.year,
                    month=d.month,
                    selected_date=d,
                    doctor_id=filters.doctor_id,
                    status_filter=filters.status_filter,
                    full_page=filters.full_page,
                    view_mode='week',
                ),
                day=d,
            ),
        })

    if week_start.year == week_end.year:
        period_label = f"{week_start.strftime('%b %d')} – {week_end.strftime('%b %d, %Y')}"
    else:
        period_label = f"{week_start.strftime('%b %d, %Y')} – {week_end.strftime('%b %d, %Y')}"

    nav = build_calendar_nav_urls(filters)
    return {
        'calendar_week_days': days,
        'calendar_week_start': week_start,
        'calendar_week_end': week_end,
        'calendar_period_label': period_label,
        'calendar_selected_date': selected,
        'calendar_selected_iso': selected.isoformat(),
        'calendar_today_iso': today.isoformat(),
        'calendar_nav_prev_url': nav['prev'],
        'calendar_nav_next_url': nav['next'],
        'calendar_nav_today_url': nav['today'],
        'calendar_viewer_role': normalize_role(user.role),
        'calendar_view_mode': 'week',
    }


def build_calendar_day_context(
    user,
    filters: CalendarFilters,
) -> dict[str, Any]:
    """Context for day agenda partial."""
    selected = filters.selected_date
    statuses = statuses_for_filter(filters.status_filter)
    if filters.status_filter:
        events = get_events_by_date(
            user,
            selected,
            selected,
            doctor_id=filters.doctor_id,
            statuses=statuses,
        ).get(selected, [])
    else:
        events = get_combined_events_by_date(
            user,
            selected,
            selected,
            doctor_id=filters.doctor_id,
            statuses=statuses,
        ).get(selected, [])

    return {
        'calendar_selected_date': selected,
        'calendar_selected_label': f"{selected.strftime('%A, %B')} {selected.day}",
        'calendar_day_events': events,
        'calendar_viewer_role': normalize_role(user.role),
        'calendar_is_today': selected == timezone.localdate(),
        'calendar_status_filter': filters.status_filter or '',
    }


def build_calendar_body_context(user, filters: CalendarFilters) -> dict[str, Any]:
    """Month or week grid context for the main calendar pane."""
    if filters.view_mode == 'week':
        return build_calendar_week_context(user, filters)
    return build_calendar_month_context(user, filters)


def build_calendar_context(user, filters: CalendarFilters) -> dict[str, Any]:
    """Full calendar shell / fragment context."""
    body_ctx = build_calendar_body_context(user, filters)
    day_ctx = build_calendar_day_context(user, filters)
    filter_ctx = build_calendar_filters_context(user, filters)
    period_label = body_ctx.get('calendar_period_label') or body_ctx.get('calendar_month_label', '')
    return {
        **body_ctx,
        **day_ctx,
        **filter_ctx,
        'calendar_period_label': period_label,
        'calendar_embedded': not filters.full_page,
    }


def _ics_datetime(d: date, t) -> str:
    from django.utils import timezone as tz

    if t:
        dt = datetime.combine(d, t)
        if tz.is_aware(dt):
            dt = tz.localtime(dt)
        else:
            dt = tz.make_aware(dt, tz.get_current_timezone())
        return dt.strftime('%Y%m%dT%H%M%S')
    return d.strftime('%Y%m%d')


def build_ics_calendar(user, filters: CalendarFilters) -> str:
    """Generate ICS for appointments in the current calendar range."""
    if filters.view_mode == 'week':
        start, end = week_bounds(filters.selected_date)
    else:
        start, end = month_bounds(filters.year, filters.month)

    events_by_date = get_events_by_date(
        user,
        start,
        end,
        doctor_id=filters.doctor_id,
        statuses=statuses_for_filter(filters.status_filter),
    )
    lines = [
        'BEGIN:VCALENDAR',
        'VERSION:2.0',
        'PRODID:-//JMCFI Clinic//Appointments//EN',
        'CALSCALE:GREGORIAN',
        'METHOD:PUBLISH',
    ]
    for day_events in events_by_date.values():
        for event in day_events:
            if event.get('event_kind') != 'appointment':
                continue
            uid = f"appt-{event['id']}@jmcfi-clinic"
            dtstamp = timezone.now().strftime('%Y%m%dT%H%M%SZ')
            dtstart = _ics_datetime(event['date'], event['time'])
            lines.extend([
                'BEGIN:VEVENT',
                f'UID:{uid}',
                f'DTSTAMP:{dtstamp}',
                f'DTSTART:{dtstart}',
                f'SUMMARY:{event["title"]}',
                f'DESCRIPTION:{event.get("meta_line", "")}',
                f'URL:{event["detail_url"]}',
                'END:VEVENT',
            ])
    lines.append('END:VCALENDAR')
    return '\r\n'.join(lines) + '\r\n'


def build_dashboard_calendar_context(
    user,
    *,
    selected_date: date | None = None,
    get_params=None,
) -> dict[str, Any]:
    """Initial calendar context for dashboard embed."""
    today = timezone.localdate()
    if get_params is not None:
        filters = parse_calendar_filters(get_params, user, today=today)
    else:
        selected = selected_date or today
        filters = CalendarFilters(
            year=selected.year,
            month=selected.month,
            selected_date=selected,
        )
    return build_calendar_context(user, filters)


def build_admin_calendar_context(
    *,
    year: int | None = None,
    month: int | None = None,
    selected_date: date | None = None,
) -> dict[str, Any]:
    """Admin analytics heat-map month grid."""
    today = timezone.localdate()
    year = year or today.year
    month = month or today.month
    selected = _clamp_selected_date(selected_date or today, year, month, today)
    start, end = month_bounds(year, month)
    counts = get_daily_counts(start, end)

    weeks: list[list[dict[str, Any]]] = []
    for week in build_month_weeks(year, month):
        week_cells = []
        for cell in week:
            d = cell['date']
            count = counts.get(d, 0)
            level = _heat_level(count)
            week_cells.append({
                **cell,
                'is_today': d == today,
                'is_selected': d == selected,
                'event_count': count,
                'heat_level': level,
                'heat_class': HEAT_LEVEL_CLASSES[level],
                'list_url': appointment_list_url_for_date(d),
            })
        weeks.append(week_cells)

    if month == 1:
        prev_year, prev_month = year - 1, 12
    else:
        prev_year, prev_month = year, month - 1
    if month == 12:
        next_year, next_month = year + 1, 1
    else:
        next_year, next_month = year, month + 1

    def admin_cal_url(y: int, m: int, d: date | None = None) -> str:
        p: dict[str, str | int] = {'year': y, 'month': m}
        if d:
            p['date'] = d.isoformat()
        return f"{reverse('analytics:dashboard')}?{urlencode(p)}"

    return {
        'admin_calendar_weeks': weeks,
        'calendar_weekday_labels': WEEKDAY_LABELS,
        'admin_calendar_month_label': date(year, month, 1).strftime('%B %Y'),
        'admin_calendar_selected_date': selected,
        'admin_calendar_nav_prev_url': admin_cal_url(prev_year, prev_month, selected),
        'admin_calendar_nav_next_url': admin_cal_url(next_year, next_month, selected),
        'admin_calendar_nav_today_url': admin_cal_url(today.year, today.month, today),
        'admin_calendar_selected_list_url': appointment_list_url_for_date(selected),
    }
