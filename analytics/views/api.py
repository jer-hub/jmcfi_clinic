"""JSON API endpoints for chart / calendar data."""

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone

from core.decorators import role_required
from core.utils import parse_date

from analytics.services import (
    academic_correlation_data,
    appointment_by_hour,
    appointment_by_type,
    appointment_volume,
    financial_summary,
    illness_stats,
    population_health_data,
    student_demographics,
)
from analytics.views.helpers import _filters_from_request, _get_date_range


@login_required
@role_required('admin')
def admin_calendar_month_api(request):
    """JSON month payload for admin dashboard heat-map (Alpine navigation)."""
    from appointments.calendar_service import build_admin_calendar_context

    today = timezone.localdate()
    try:
        cal_year = int(request.GET.get('year', today.year))
    except (TypeError, ValueError):
        cal_year = today.year
    try:
        cal_month = int(request.GET.get('month', today.month))
    except (TypeError, ValueError):
        cal_month = today.month
    cal_month = max(1, min(12, cal_month))
    cal_selected = parse_date(request.GET.get('date', '')) or today

    ctx = build_admin_calendar_context(
        year=cal_year,
        month=cal_month,
        selected_date=cal_selected,
        user=request.user,
    )
    return JsonResponse(ctx['admin_calendar_client'])


@login_required
@role_required('staff', 'doctor', 'admin')
def chart_data_api(request):
    """Return JSON chart data for AJAX requests on the dashboard."""
    chart = request.GET.get('chart', '')
    date_from, date_to = _get_date_range(request)
    filters = _filters_from_request(request)

    data = {}

    if chart == 'appointment_volume':
        raw = appointment_volume(date_from, date_to, filters=filters)
        data = {
            'labels': [r['day'].strftime('%Y-%m-%d') for r in raw],
            'values': [r['count'] for r in raw],
        }

    elif chart == 'appointment_by_type':
        raw = appointment_by_type(date_from, date_to, filters=filters)
        data = {
            'labels': [r['appointment_type'] for r in raw],
            'values': [r['count'] for r in raw],
        }

    elif chart == 'hourly_distribution':
        raw = appointment_by_hour(date_from, date_to, filters=filters)
        data = {
            'labels': [f"{r['hour']}:00" for r in raw],
            'values': [r['count'] for r in raw],
        }

    elif chart == 'illness_stats':
        raw = illness_stats(date_from, date_to, filters=filters)[:15]
        data = {
            'labels': [r['diagnosis'] for r in raw],
            'values': [r['count'] for r in raw],
        }

    elif chart == 'demographics_course':
        demo = student_demographics(filters=filters)
        data = {
            'labels': [r['course'] for r in demo['course']],
            'values': [r['count'] for r in demo['course']],
        }

    elif chart == 'demographics_department':
        demo = student_demographics(filters=filters)
        data = {
            'labels': [r['department'] for r in demo['department']],
            'values': [r['count'] for r in demo['department']],
        }

    elif chart == 'demographics_year':
        demo = student_demographics(filters=filters)
        data = {
            'labels': [r['year_level'] for r in demo['year_level']],
            'values': [r['count'] for r in demo['year_level']],
        }

    elif chart == 'population_health_by_department':
        pop = population_health_data(date_from, date_to, filters=filters)
        raw = pop['health_by_department']
        data = {
            'labels': [
                r['patient__patient_profile__department'] or 'Unknown'
                for r in raw
            ],
            'values': [r['count'] for r in raw],
        }

    elif chart == 'appointments_by_department':
        pop = population_health_data(date_from, date_to, filters=filters)
        raw = pop['appt_by_department']
        data = {
            'labels': [
                r['patient__patient_profile__department'] or 'Unknown'
                for r in raw
            ],
            'values': [r['count'] for r in raw],
        }

    elif chart == 'appointments_by_year':
        pop = population_health_data(date_from, date_to, filters=filters)
        raw = pop['appt_by_year']
        data = {
            'labels': [
                r['patient__patient_profile__year_level'] or 'Unknown'
                for r in raw
            ],
            'values': [r['count'] for r in raw],
        }

    elif chart == 'financial_category':
        raw = financial_summary(date_from, date_to)['by_category']
        data = {
            'labels': [r['category'] for r in raw],
            'values': [float(r['total']) for r in raw],
        }

    elif chart == 'academic_visits_by_department':
        acad = academic_correlation_data(date_from, date_to, filters=filters)
        raw = acad['visits_by_department']
        data = {
            'labels': [
                r['patient__patient_profile__department'] or 'Unknown'
                for r in raw
            ],
            'values': [r['count'] for r in raw],
        }

    elif chart == 'academic_visits_by_course':
        acad = academic_correlation_data(date_from, date_to, filters=filters)
        raw = acad['visits_by_course']
        data = {
            'labels': [
                r['patient__patient_profile__course'] or 'Unknown'
                for r in raw
            ],
            'values': [r['count'] for r in raw],
        }

    elif chart == 'academic_emergency_by_course':
        acad = academic_correlation_data(date_from, date_to, filters=filters)
        raw = acad['emergency_visits']
        data = {
            'labels': [
                r['patient__patient_profile__course'] or 'Unknown'
                for r in raw
            ],
            'values': [r['count'] for r in raw],
        }

    return JsonResponse(data)
