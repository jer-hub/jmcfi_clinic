"""Health trend analysis views."""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from core.decorators import role_required

from analytics.academic_filters import analytics_filter_context
from analytics.forms import HealthTrendFilterForm
from analytics.services import (
    filtered_health_trend_records,
    illness_source_counts,
    illness_stats,
)
from analytics.views.helpers import (
    _filters_from_request,
    _get_date_range,
    _period_presets_for_request,
)


@login_required
@role_required('staff', 'doctor', 'admin')
def health_trends(request):
    """Student health trend analysis across semesters."""
    date_from, date_to = _get_date_range(request)
    filters = _filters_from_request(request)
    illness_form = HealthTrendFilterForm(request.GET or None)
    trends = filtered_health_trend_records(request)
    illness_q = (request.GET.get('illness_category') or '').strip() if request.GET else ''

    live_illness = illness_stats(
        date_from, date_to,
        diagnosis_query=illness_q or None,
        filters=filters,
    )

    live_illness_stats = live_illness[:20]
    live_medical_cases, live_dental_cases = illness_source_counts(
        date_from, date_to, diagnosis_query=illness_q or None, filters=filters,
    )
    context = {
        'illness_filter_form': illness_form,
        'trends': trends,
        'trends_count': trends.count(),
        'live_illness_stats': live_illness_stats,
        'live_cases_total': sum(item['count'] for item in live_illness_stats),
        'live_medical_cases': live_medical_cases,
        'live_dental_cases': live_dental_cases,
        'illness_filter': illness_q,
        'date_from': date_from,
        'date_to': date_to,
        'show_illness_filter': True,
        'export_variant': 'health_trends',
        'trends_scope_hint': 'Clinic-wide historical aggregates',
        'live_scope_hint': 'Filtered by date and academic segment',
    }
    context.update(analytics_filter_context(request, date_from, date_to))
    context['period_presets'] = _period_presets_for_request(request, date_from, date_to)
    illness_extra = ''
    if illness_q:
        from urllib.parse import quote
        illness_extra = f'&illness_category={quote(illness_q)}'
    context['extra_query'] = illness_extra
    context['export_query'] = context['academic_query'] + illness_extra
    return render(request, 'analytics/health_trends.html', context)
