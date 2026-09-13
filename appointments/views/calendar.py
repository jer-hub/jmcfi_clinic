"""Appointment calendar views."""

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render

from appointments.calendar_service import (
    CalendarFilters,
    build_calendar_context,
    build_calendar_page_url,
    build_ics_calendar,
    parse_calendar_filters,
)
from core.decorators import role_required


def _calendar_filters_from_request(request, *, full_page: bool = False):
    filters = parse_calendar_filters(request.GET, request.user, full_page=full_page)
    if full_page or request.GET.get('full') == '1':
        filters = CalendarFilters(
            year=filters.year,
            month=filters.month,
            selected_date=filters.selected_date,
            doctor_id=filters.doctor_id,
            status_filter=filters.status_filter,
            event_filter=filters.event_filter,
            full_page=True,
            view_mode=filters.view_mode,
        )
    return filters


def _calendar_htmx_response(request, template, context, filters):
    response = render(request, template, context)
    if filters.full_page:
        response['HX-Push-Url'] = build_calendar_page_url(filters)
    return response


@login_required
@role_required('student', 'staff', 'doctor')
def appointment_calendar(request):
    """Full-page appointment calendar."""
    filters = _calendar_filters_from_request(request, full_page=True)
    context = build_calendar_context(request.user, filters)
    context['calendar_embedded'] = False
    return render(request, 'appointments/calendar.html', context)


@login_required
@role_required('student', 'staff', 'doctor')
def calendar_body_fragment(request):
    """HTMX: month/week grid + day panel refresh."""
    filters = _calendar_filters_from_request(request)
    context = build_calendar_context(request.user, filters)
    return _calendar_htmx_response(
        request,
        'components/calendar/_calendar_body.html',
        context,
        filters,
    )


# Backward-compatible name for bookmarks/tests
calendar_month_fragment = calendar_body_fragment


@login_required
@role_required('student', 'staff', 'doctor')
def calendar_export_ics(request):
    """Download ICS for visible calendar range."""
    filters = _calendar_filters_from_request(request)
    ics_body = build_ics_calendar(request.user, filters)
    response = HttpResponse(ics_body, content_type='text/calendar; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="clinic-schedule.ics"'
    return response


@login_required
@role_required('student', 'staff', 'doctor')
def calendar_day_fragment(request):
    """HTMX: day agenda panel."""
    filters = _calendar_filters_from_request(request)
    context = build_calendar_context(request.user, filters)
    return _calendar_htmx_response(
        request,
        'components/calendar/_day_agenda.html',
        context,
        filters,
    )
