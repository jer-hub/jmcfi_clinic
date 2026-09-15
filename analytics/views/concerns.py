"""Concern record analytics views."""

from urllib.parse import quote

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from core.decorators import role_required

from analytics.academic_filters import analytics_filter_context
from analytics.services import (
    concern_by_affiliation,
    concern_by_department,
    concern_kpis,
    concern_volume_by_day,
    filtered_concern_records,
)
from analytics.views.helpers import (
    _filters_from_request,
    _get_date_range,
    _period_presets_for_request,
)


@login_required
@role_required('staff', 'doctor', 'admin')
def concerns_analysis(request):
    """Clinic-wide concern log analysis for the selected period."""
    date_from, date_to = _get_date_range(request)
    filters = _filters_from_request(request)
    concern_q = (request.GET.get('q') or '').strip()

    kpis = concern_kpis(date_from, date_to, filters=filters, search=concern_q or None)
    by_affiliation = concern_by_affiliation(
        date_from, date_to, filters=filters, search=concern_q or None,
    )
    by_department = concern_by_department(
        date_from, date_to, filters=filters, search=concern_q or None,
    )
    volume_by_day = concern_volume_by_day(
        date_from, date_to, filters=filters, search=concern_q or None,
    )
    recent_records = list(
        filtered_concern_records(
            date_from, date_to, filters=filters, search=concern_q or None,
        ).order_by('-date', '-time', '-id')[:25]
    )

    affiliation_max = by_affiliation[0]['count'] if by_affiliation else 0
    department_max = by_department[0]['count'] if by_department else 0

    context = {
        'date_from': date_from,
        'date_to': date_to,
        'export_variant': 'concerns',
        'show_concern_search': True,
        'kpis': kpis,
        'by_affiliation': by_affiliation,
        'by_department': by_department,
        'affiliation_max': affiliation_max,
        'department_max': department_max,
        'volume_by_day': volume_by_day,
        'recent_records': recent_records,
        'scope_hint': 'Filtered by visit date and academic segment',
    }
    context.update(analytics_filter_context(request, date_from, date_to))
    context['period_presets'] = _period_presets_for_request(request, date_from, date_to)
    concern_extra = ''
    if concern_q:
        concern_extra = f'&q={quote(concern_q)}'
    context['extra_query'] = concern_extra
    context['export_query'] = context['academic_query'] + concern_extra
    return render(request, 'analytics/concerns_analysis.html', context)
