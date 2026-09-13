"""Academic correlation views."""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from core.decorators import role_required

from analytics.academic_filters import analytics_filter_context
from analytics.services import academic_correlation_data
from analytics.views.helpers import (
    _filters_from_request,
    _get_date_range,
    _period_presets_for_request,
)


@login_required
@role_required('staff', 'doctor', 'admin')
def academic_correlation(request):
    """Correlate health data with academic indicators (absenteeism)."""
    date_from, date_to = _get_date_range(request)
    filters = _filters_from_request(request)
    context = academic_correlation_data(date_from, date_to, filters=filters)
    context.update({
        'period_hint': f'{date_from.strftime("%b %d")} – {date_to.strftime("%b %d")}',
        'date_from': date_from,
        'date_to': date_to,
        'export_variant': 'academic',
    })
    context.update(analytics_filter_context(request, date_from, date_to))
    context['period_presets'] = _period_presets_for_request(request, date_from, date_to)
    return render(request, 'analytics/academic_correlation.html', context)
