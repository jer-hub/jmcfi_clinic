"""Population health dashboard views."""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from core.decorators import role_required

from analytics.academic_filters import analytics_filter_context
from analytics.services import population_health_data
from analytics.views.helpers import (
    _filters_from_request,
    _get_date_range,
    _period_presets_for_request,
)


@login_required
@role_required('staff', 'doctor', 'admin')
def population_health(request):
    """Population health dashboard by demographics."""
    date_from, date_to = _get_date_range(request)
    filters = _filters_from_request(request)
    context = population_health_data(date_from, date_to, filters=filters)
    context.update({
        'period_hint': f'{date_from.strftime("%b %d")} – {date_to.strftime("%b %d")}',
        'date_from': date_from,
        'date_to': date_to,
        'export_variant': 'population',
    })
    context.update(analytics_filter_context(request, date_from, date_to))
    context['period_presets'] = _period_presets_for_request(request, date_from, date_to)
    return render(request, 'analytics/population_health.html', context)
