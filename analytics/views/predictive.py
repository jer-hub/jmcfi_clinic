"""Predictive analytics views."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import redirect, render
from django.urls import reverse

from core.decorators import admin_required, role_required
from core.utils import paginate_queryset

from analytics.academic_filters import (
    academic_filter_query_string,
    analytics_filter_context,
    apply_academic_filters,
    page_window_numbers,
)
from analytics.models import PredictiveInsight
from analytics.services import (
    appointment_by_hour,
    appointment_by_weekday,
    illness_stats,
)
from analytics.views.helpers import (
    _filters_from_request,
    _get_date_range,
    _period_presets_for_request,
)


@login_required
@role_required('staff', 'doctor', 'admin')
def predictive_analytics(request):
    """View predictive insights & generate new ones."""
    insights = PredictiveInsight.objects.all()

    insight_filter = request.GET.get('type', '')
    if insight_filter:
        insights = insights.filter(insight_type=insight_filter)

    date_from, date_to = _get_date_range(request)
    filters = _filters_from_request(request)
    hourly = appointment_by_hour(date_from, date_to, filters=filters)
    weekday = appointment_by_weekday(date_from, date_to, filters=filters)

    peak_hour = max(hourly, key=lambda x: x['count'])['hour'] if hourly else None
    busiest_day = max(weekday, key=lambda x: x['count'])['weekday'] if weekday else None

    day_names = {1: 'Sunday', 2: 'Monday', 3: 'Tuesday', 4: 'Wednesday',
                 5: 'Thursday', 6: 'Friday', 7: 'Saturday'}

    insights_page = paginate_queryset(insights, request, per_page=10)
    context = {
        'insights': insights_page,
        'page_window': page_window_numbers(insights_page),
        'insight_types': PredictiveInsight.INSIGHT_TYPES,
        'selected_type': insight_filter,
        'peak_hour': peak_hour,
        'peak_hour_display': f'{peak_hour:02d}:00' if peak_hour is not None else 'N/A',
        'busiest_day': day_names.get(busiest_day, 'N/A'),
        'period_hint': f'{date_from.strftime("%b %d")} – {date_to.strftime("%b %d")}',
        'hourly_data': hourly,
        'weekday_data': weekday,
        'day_names': day_names,
        'date_from': date_from,
        'date_to': date_to,
        'export_variant': 'predictive',
    }
    context.update(analytics_filter_context(request, date_from, date_to))
    context['period_presets'] = _period_presets_for_request(request, date_from, date_to)
    if insight_filter:
        from urllib.parse import quote
        context['extra_query'] = f'&type={quote(insight_filter)}'
    return render(request, 'analytics/predictive_analytics.html', context)


@login_required
@admin_required
def generate_predictive_insight(request):
    """Generate a new predictive insight based on historical data."""
    if request.method != 'POST':
        return redirect('analytics:predictive_analytics')

    insight_type = request.POST.get('insight_type', 'peak_hours')
    date_from, date_to = _get_date_range(request)
    filters = _filters_from_request(request)

    data = {}
    title = ''
    description = ''
    risk_level = 'low'

    if insight_type == 'peak_hours':
        hourly = appointment_by_hour(date_from, date_to, filters=filters)
        peak = max(hourly, key=lambda x: x['count']) if hourly else {'hour': 0, 'count': 0}
        title = f"Peak Hours Analysis ({date_from} to {date_to})"
        description = f"Highest appointment volume at {peak['hour']}:00 with {peak['count']} appointments."
        data = {'hourly': hourly, 'peak': peak, 'academic_filters': filters}

    elif insight_type == 'medicine_demand':
        illness = illness_stats(date_from, date_to, filters=filters)
        title = f"Medicine Demand Forecast ({date_from} to {date_to})"
        top = illness[:5] if illness else []
        top_names = ', '.join([i['diagnosis'] for i in top]) if top else 'None'
        description = f"Top diagnoses driving demand: {top_names}. Plan supplies accordingly."
        data = {'top_diagnoses': illness[:10], 'academic_filters': filters}

    elif insight_type == 'staff_workload':
        from appointments.models import Appointment
        staff_load = list(
            apply_academic_filters(
                Appointment.objects.filter(
                    date__gte=date_from, date__lte=date_to, status='completed',
                ),
                filters,
            )
            .values('doctor__first_name', 'doctor__last_name')
            .annotate(count=Count('id'))
            .order_by('-count')[:10]
        )
        title = f"Staff Workload ({date_from} to {date_to})"
        description = f"Workload distribution across {len(staff_load)} clinicians."
        data = {'staff_load': staff_load, 'academic_filters': filters}

    elif insight_type == 'outbreak_risk':
        illness = illness_stats(date_from, date_to, filters=filters)
        total = sum(i['count'] for i in illness)
        top = illness[0] if illness else None
        if top and total:
            pct = round(top['count'] / total * 100, 1)
            risk_level = 'critical' if pct > 40 else 'high' if pct > 25 else 'moderate' if pct > 15 else 'low'
            title = f"Outbreak Risk – {top['diagnosis']}"
            description = f"{top['diagnosis']} accounts for {pct}% of cases ({top['count']}/{total})."
        else:
            title = "Outbreak Risk Assessment"
            description = "Insufficient data to assess outbreak risk."
        data = {'illness_stats': illness[:10], 'total_cases': total, 'academic_filters': filters}

    PredictiveInsight.objects.create(
        insight_type=insight_type,
        title=title,
        description=description,
        data_json=data,
        risk_level=risk_level,
        period_start=date_from,
        period_end=date_to,
        generated_by=request.user,
    )
    messages.success(request, f'Predictive insight "{title}" generated successfully.')
    query = f'date_from={date_from.isoformat()}&date_to={date_to.isoformat()}'
    academic_q = academic_filter_query_string(filters)
    if academic_q:
        query += academic_q
    return redirect(f"{reverse('analytics:predictive_analytics')}?{query}")
