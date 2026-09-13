"""Resource utilization views."""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from core.decorators import role_required
from core.utils import paginate_queryset

from analytics.academic_filters import analytics_filter_context, page_window_numbers
from analytics.services import (
    resource_utilization_kpis,
    resource_utilization_staff_stats,
    utilization_records_qs,
)
from analytics.views.helpers import (
    _filters_from_request,
    _get_date_range,
    _period_presets_for_request,
)


@login_required
@role_required('staff', 'doctor', 'admin')
def resource_utilization(request):
    """Resource utilization overview."""
    date_from, date_to = _get_date_range(request)
    filters = _filters_from_request(request)
    records = utilization_records_qs(date_from, date_to)
    avg_consultation, total_throughput, avg_throughput = resource_utilization_kpis(records)
    staff_stats = resource_utilization_staff_stats(date_from, date_to, filters=filters)
    staff_total_completed = sum(s['total'] for s in staff_stats)

    records_page = paginate_queryset(records, request, per_page=15)
    context = {
        'records': records_page,
        'page_window': page_window_numbers(records_page),
        'avg_consultation': avg_consultation,
        'avg_consultation_display': f'{avg_consultation} min',
        'total_throughput': total_throughput,
        'avg_throughput': avg_throughput,
        'staff_stats': staff_stats,
        'staff_total_completed': staff_total_completed,
        'period_hint': f'{date_from.strftime("%b %d")} – {date_to.strftime("%b %d")}',
        'date_from': date_from,
        'date_to': date_to,
        'export_variant': 'resources',
        'clinic_wide_hint': 'Clinic-wide daily log (not academic-filtered)',
        'staff_scope_hint': 'Filtered by selected academic segment',
    }
    context.update(analytics_filter_context(request, date_from, date_to))
    context['period_presets'] = _period_presets_for_request(request, date_from, date_to)
    return render(request, 'analytics/resource_utilization.html', context)
