"""Patient chart analytics views."""

from urllib.parse import quote

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from core.decorators import role_required

from analytics.academic_filters import analytics_filter_context
from analytics.services import (
    filtered_patient_chart_entries,
    patient_chart_by_department,
    patient_chart_by_designation,
    patient_chart_by_status,
    patient_chart_entry_volume_by_day,
    patient_chart_kpis,
)
from analytics.views.helpers import (
    _filters_from_request,
    _get_date_range,
    _period_presets_for_request,
)


@login_required
@role_required('staff', 'doctor', 'admin')
def patient_charts_analysis(request):
    """Clinic-wide patient chart analysis for the selected period."""
    date_from, date_to = _get_date_range(request)
    filters = _filters_from_request(request)
    chart_q = (request.GET.get('q') or '').strip()

    kpis = patient_chart_kpis(date_from, date_to, filters=filters, search=chart_q or None)
    by_status = patient_chart_by_status(
        date_from, date_to, filters=filters, search=chart_q or None,
    )
    by_designation = patient_chart_by_designation(
        date_from, date_to, filters=filters, search=chart_q or None,
    )
    by_department = patient_chart_by_department(
        date_from, date_to, filters=filters, search=chart_q or None,
    )
    volume_by_day = patient_chart_entry_volume_by_day(
        date_from, date_to, filters=filters, search=chart_q or None,
    )
    recent_entries = list(
        filtered_patient_chart_entries(
            date_from, date_to, filters=filters, search=chart_q or None,
        ).order_by('-date_and_time', '-id')[:25]
    )

    status_max = by_status[0]['count'] if by_status else 0
    designation_max = by_designation[0]['count'] if by_designation else 0
    department_max = by_department[0]['count'] if by_department else 0

    context = {
        'date_from': date_from,
        'date_to': date_to,
        'export_variant': 'patient_charts',
        'show_concern_search': True,
        'kpis': kpis,
        'by_status': by_status,
        'by_designation': by_designation,
        'by_department': by_department,
        'status_max': status_max,
        'designation_max': designation_max,
        'department_max': department_max,
        'volume_by_day': volume_by_day,
        'recent_entries': recent_entries,
        'scope_hint': 'Charts by created date; entries by consultation date',
    }
    context.update(analytics_filter_context(request, date_from, date_to))
    context['period_presets'] = _period_presets_for_request(request, date_from, date_to)
    chart_extra = ''
    if chart_q:
        chart_extra = f'&q={quote(chart_q)}'
    context['extra_query'] = chart_extra
    context['export_query'] = context['academic_query'] + chart_extra
    return render(request, 'analytics/patient_charts_analysis.html', context)
