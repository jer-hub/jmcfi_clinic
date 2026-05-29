import json
import csv
import io
from collections import defaultdict, OrderedDict
from datetime import timedelta, datetime
from decimal import Decimal

from django.db import models
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse, HttpResponseForbidden
from django.db.models import (
    Count, Avg, Sum, Q, F, Min, Max, ExpressionWrapper,
    FloatField, DurationField
)
from django.db.models.functions import (
    TruncMonth, TruncDate, TruncHour, ExtractHour, ExtractWeekDay, Cast
)
from django.utils import timezone
from django.contrib.auth import get_user_model

from core.decorators import role_required, admin_required
from core.roles import PATIENT_ROLE_VALUES, is_patient_role
from core.utils import paginate_queryset, parse_date, apply_date_filters

from .models import (
    HealthTrendRecord, PredictiveInsight, ResourceUtilization,
    ComplianceReport, FinancialRecord, ExportLog,
)
from .forms import (
    HealthTrendFilterForm, FinancialRecordForm, ComplianceReportForm,
    DateRangeFilterForm, ExportForm,
)

User = get_user_model()


# =====================================================================
# Helper: collect cross-app stats used by multiple views
# =====================================================================

def _get_date_range(request):
    """Extract date_from / date_to from GET params with sensible defaults."""
    date_from = parse_date(request.GET.get('date_from'))
    date_to = parse_date(request.GET.get('date_to'))
    if not date_to:
        date_to = timezone.now().date()
    if not date_from:
        date_from = date_to - timedelta(days=90)
    return date_from, date_to


def _period_presets(date_from, date_to):
    """Quick date-range shortcuts for analytics filter bars."""
    today = timezone.localdate()
    presets = []
    for label, days in (('30 days', 30), ('90 days', 90), ('6 months', 180)):
        preset_from = today - timedelta(days=days)
        presets.append({
            'label': label,
            'date_from': preset_from,
            'date_to': today,
            'active': date_from == preset_from and date_to == today,
        })
    return presets


def _friendly_diagnosis_label(value):
    """Normalize diagnosis labels for chart/list display."""
    text = (value or '').strip()
    if not text:
        return 'Unspecified diagnosis'
    text = ' '.join(text.replace('_', ' ').split())
    if text.islower():
        return text.title()
    return text


def _diagnosis_aggregate_key(value):
    """Bucket placeholder diagnoses so lists stay readable."""
    text = _friendly_diagnosis_label(value)
    key = text.lower().strip('.')
    if key in {'diagnosis', 'diag', 'unspecified diagnosis', 'n/a', 'na', 'none', 'test'}:
        return '__unspecified__'
    if len(key) <= 12 and key.startswith('diag'):
        return '__unspecified__'
    return key


def _diagnosis_display_name(key, sample_value):
    if key == '__unspecified__':
        return 'Unspecified / general'
    return _friendly_diagnosis_label(sample_value)


def _student_visit_history(user, months=6):
    """Last N calendar months of appointment counts (zeros for quiet months)."""
    from appointments.models import Appointment

    now = timezone.now()
    month_starts = []
    cursor = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    for _ in range(months):
        month_starts.append(cursor)
        if cursor.month == 1:
            cursor = cursor.replace(year=cursor.year - 1, month=12)
        else:
            cursor = cursor.replace(month=cursor.month - 1)
    month_starts.reverse()

    raw = (
        Appointment.objects.filter(patient=user)
        .annotate(month=TruncMonth(Cast('date', output_field=models.DateTimeField())))
        .values('month')
        .annotate(count=Count('id'))
    )
    count_map = {}
    for row in raw:
        month_val = row['month']
        if not month_val:
            continue
        if timezone.is_aware(month_val):
            month_val = timezone.localtime(month_val)
        count_map[(month_val.year, month_val.month)] = row['count']

    return [
        {
            'month': month_start,
            'label': month_start.strftime('%b %Y'),
            'count': count_map.get((month_start.year, month_start.month), 0),
        }
        for month_start in month_starts
    ]


def _illness_stats(date_from, date_to, doctor=None, diagnosis_query=None):
    """Aggregate diagnosis signals from medical records plus dental encounters.

    Optional `doctor` scope limits results to records handled by that clinician.
    Optional `diagnosis_query` filters medical records and ranked results (icontains).
    """
    from medical_records.models import MedicalRecord
    from dental_records.models import DentalRecord

    medical_qs = MedicalRecord.objects.filter(
        created_at__date__gte=date_from,
        created_at__date__lte=date_to,
    ).exclude(diagnosis='')

    dental_qs = DentalRecord.objects.filter(
        date_of_examination__gte=date_from,
        date_of_examination__lte=date_to,
    )

    if diagnosis_query:
        medical_qs = medical_qs.filter(diagnosis__icontains=diagnosis_query)

    if doctor is not None:
        medical_qs = medical_qs.filter(doctor=doctor)
        dental_qs = dental_qs.filter(examined_by=doctor)

    aggregated = defaultdict(int)
    display_names = {}

    for item in medical_qs.values('diagnosis').annotate(count=Count('id')):
        key = _diagnosis_aggregate_key(item['diagnosis'])
        aggregated[key] += item['count']
        if key not in display_names:
            display_names[key] = _diagnosis_display_name(key, item['diagnosis'])

    dental_count = dental_qs.count()
    if dental_count:
        aggregated['__dental__'] += dental_count
        display_names.setdefault('__dental__', 'Dental consultation')

    results = [
        {'diagnosis': display_names[key], 'count': count}
        for key, count in sorted(aggregated.items(), key=lambda x: x[1], reverse=True)
    ]
    if diagnosis_query:
        needle = diagnosis_query.lower()
        results = [
            item for item in results
            if needle in item['diagnosis'].lower()
        ]
    return results


def _appointment_volume(date_from, date_to):
    """Appointment counts grouped by date."""
    from appointments.models import Appointment
    return list(
        Appointment.objects.filter(date__gte=date_from, date__lte=date_to)
        .values(day=F('date'))
        .annotate(count=Count('id'))
        .order_by('day')
    )


def _appointment_by_type(date_from, date_to):
    from appointments.models import Appointment
    return list(
        Appointment.objects.filter(date__gte=date_from, date__lte=date_to)
        .values('appointment_type')
        .annotate(count=Count('id'))
        .order_by('-count')
    )


def _appointment_by_hour(date_from, date_to, doctor=None):
    from appointments.models import Appointment
    qs = Appointment.objects.filter(date__gte=date_from, date__lte=date_to)
    if doctor is not None:
        qs = qs.filter(doctor=doctor)
    return list(
        qs.annotate(hour=ExtractHour('time'))
        .values('hour')
        .annotate(count=Count('id'))
        .order_by('hour')
    )


def _hourly_chart_series(hourly_rows):
    """Normalize sparse hour aggregates into a full 0–23 series for charts."""
    count_by_hour = {int(row['hour']): row['count'] for row in hourly_rows}
    series = [
        {
            'hour': hour,
            'count': count_by_hour.get(hour, 0),
            'label': f'{hour:02d}:00',
        }
        for hour in range(24)
    ]
    peak = max(series, key=lambda row: row['count'])
    has_data = peak['count'] > 0
    return series, peak if has_data else None, has_data


def _appointment_by_weekday(date_from, date_to):
    from appointments.models import Appointment
    return list(
        Appointment.objects.filter(date__gte=date_from, date__lte=date_to)
        .annotate(weekday=ExtractWeekDay('date'))
        .values('weekday')
        .annotate(count=Count('id'))
        .order_by('weekday')
    )


def _student_demographics():
    """Demographics breakdown from StudentProfile."""
    from core.models import PatientProfile
    course = list(
        PatientProfile.objects.exclude(course='').values('course')
        .annotate(count=Count('id')).order_by('-count')
    )
    year_level = list(
        PatientProfile.objects.exclude(year_level='').values('year_level')
        .annotate(count=Count('id')).order_by('year_level')
    )
    gender = list(
        PatientProfile.objects.exclude(gender='').values('gender')
        .annotate(count=Count('id')).order_by('-count')
    )
    return {'course': course, 'year_level': year_level, 'gender': gender}


def _financial_summary(date_from, date_to):
    """Aggregate financial data for the period."""
    qs = FinancialRecord.objects.filter(date__gte=date_from, date__lte=date_to)
    total_expenses = qs.filter(is_expense=True).aggregate(total=Sum('amount'))['total'] or Decimal('0')
    total_income = qs.filter(is_expense=False).aggregate(total=Sum('amount'))['total'] or Decimal('0')
    by_category = list(
        qs.filter(is_expense=True).values('category')
        .annotate(total=Sum('amount')).order_by('-total')
    )
    monthly = list(
        qs.annotate(
            month=TruncMonth(Cast('date', output_field=models.DateTimeField()))
        )
        .values('month', 'is_expense')
        .annotate(total=Sum('amount'))
        .order_by('month')
    )
    return {
        'total_expenses': total_expenses,
        'total_income': total_income,
        'net': total_income - total_expenses,
        'by_category': by_category,
        'monthly': monthly,
    }


# =====================================================================
# 1. Main Analytics Dashboard (role-based)
# =====================================================================

@login_required
def analytics_dashboard(request):
    """Main analytics hub – role-based dashboard."""
    if request.user.role == 'admin':
        url = reverse('core:dashboard')
        query = request.META.get('QUERY_STRING', '')
        if query:
            url = f'{url}?{query}'
        return redirect(url)
    return render_analytics_dashboard(request)


@login_required
def render_analytics_dashboard(request):
    """Render analytics hub (admin home is served at / via core.dashboard)."""
    date_from, date_to = _get_date_range(request)
    user = request.user

    # Shared context
    context = {
        'date_from': date_from,
        'date_to': date_to,
        'filter_form': DateRangeFilterForm(initial={'date_from': date_from, 'date_to': date_to}),
    }

    if is_patient_role(user.role):
        # Personal health summary
        from medical_records.models import MedicalRecord
        from appointments.models import Appointment

        records = MedicalRecord.objects.filter(patient=user).order_by('-created_at')
        appointments = Appointment.objects.filter(patient=user)
        total_appointments = appointments.count()
        completed_appointments = appointments.filter(status='completed').count()
        appointment_history = _student_visit_history(user, months=6)

        recent_diag_raw = list(
            records.exclude(diagnosis='').values('diagnosis')
            .annotate(count=Count('id')).order_by('-count')[:25]
        )
        recent_diag_map = defaultdict(int)
        display_names = {}
        for item in recent_diag_raw:
            key = _diagnosis_aggregate_key(item['diagnosis'])
            recent_diag_map[key] += item['count']
            if key not in display_names:
                display_names[key] = _diagnosis_display_name(key, item['diagnosis'])

        recent_diagnoses = [
            {
                'diagnosis': display_names[key],
                'count': count,
            }
            for key, count in sorted(recent_diag_map.items(), key=lambda x: x[1], reverse=True)[:8]
        ]
        max_diagnosis_count = max((d['count'] for d in recent_diagnoses), default=0)

        completion_rate = (
            round(completed_appointments * 100 / total_appointments)
            if total_appointments
            else 0
        )

        context.update({
            'total_records': records.count(),
            'total_appointments': total_appointments,
            'completed_appointments': completed_appointments,
            'completion_rate': completion_rate,
            'completion_hint': f'{completion_rate}% completion rate' if total_appointments else 'No appointments yet',
            'appointment_history': appointment_history,
            'visit_chart_labels': [item['label'] for item in appointment_history],
            'visit_chart_data': [item['count'] for item in appointment_history],
            'visit_chart_total': sum(item['count'] for item in appointment_history),
            'recent_diagnoses': recent_diagnoses,
            'max_diagnosis_count': max_diagnosis_count,
        })

        return render(request, 'analytics/dashboard_patient.html', context)

    elif user.role in ['staff', 'doctor']:
        from appointments.models import Appointment
        from medical_records.models import MedicalRecord

        my_appointments = Appointment.objects.filter(doctor=user, date__gte=date_from, date__lte=date_to)
        hourly_series, hourly_peak, hourly_has_data = _hourly_chart_series(
            _appointment_by_hour(date_from, date_to, doctor=user),
        )
        top_diagnoses = _illness_stats(date_from, date_to, doctor=user)[:10]
        context.update({
            'total_patients': my_appointments.values('patient').distinct().count(),
            'total_consultations': my_appointments.filter(status='completed').count(),
            'pending_appointments': my_appointments.filter(status='pending').count(),
            'appointment_trend': list(
                my_appointments.values(day=F('date'))
                .annotate(count=Count('id')).order_by('day')
            ),
            'top_diagnoses': top_diagnoses,
            'top_diagnoses_total': sum(item['count'] for item in top_diagnoses),
            'hourly_distribution': hourly_series,
            'hourly_peak': hourly_peak,
            'hourly_has_data': hourly_has_data,
            'period_presets': _period_presets(date_from, date_to),
        })
        if user.role == 'staff':
            from pharmacy.services.reports import build_pharmacy_analytics_summary

            context['pharmacy_analytics'] = build_pharmacy_analytics_summary(date_from, date_to)
        return render(request, 'analytics/dashboard_staff.html', context)

    else:
        # Admin – full overview
        from appointments.models import Appointment
        from medical_records.models import MedicalRecord
        from feedback.models import Feedback

        total_patients = User.objects.filter(role__in=PATIENT_ROLE_VALUES).count()
        total_staff = User.objects.filter(role__in=['staff', 'doctor']).count()
        total_appointments = Appointment.objects.filter(date__gte=date_from, date__lte=date_to).count()
        total_records = MedicalRecord.objects.filter(created_at__date__gte=date_from, created_at__date__lte=date_to).count()
        avg_feedback = Feedback.objects.aggregate(avg=Avg('rating'))['avg'] or 0

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

        from pharmacy.services.reports import build_pharmacy_analytics_summary

        context.update({
            'total_patients': total_patients,
            'total_staff': total_staff,
            'total_appointments': total_appointments,
            'total_records': total_records,
            'avg_feedback': round(avg_feedback, 1),
            'illness_stats': _illness_stats(date_from, date_to)[:15],
            'appointment_volume': _appointment_volume(date_from, date_to),
            'appointment_by_type': _appointment_by_type(date_from, date_to),
            'appointment_by_hour': _appointment_by_hour(date_from, date_to),
            'appointment_by_weekday': _appointment_by_weekday(date_from, date_to),
            'demographics': _student_demographics(),
            'financial_summary': _financial_summary(date_from, date_to),
            'pharmacy_analytics': build_pharmacy_analytics_summary(date_from, date_to),
        })
        context.update(build_admin_calendar_context(
            year=cal_year,
            month=cal_month,
            selected_date=cal_selected,
            user=user,
        ))
        context['period_presets'] = _period_presets(date_from, date_to)
        return render(request, 'analytics/dashboard_admin.html', context)


# =====================================================================
# 2. Health Trend Analysis
# =====================================================================

def _filtered_health_trend_records(request):
    """Return HealthTrendRecord queryset matching health-trends page filters."""
    from .forms import split_health_trend_term

    trends = HealthTrendRecord.objects.all()
    if not request.GET:
        return trends
    illness_q = (request.GET.get('illness_category') or '').strip()
    term_val = (request.GET.get('term') or '').strip()
    academic_year, semester = split_health_trend_term(term_val)
    if academic_year:
        trends = trends.filter(academic_year=academic_year)
    if semester:
        trends = trends.filter(semester=semester)
    if illness_q:
        trends = trends.filter(illness_category__icontains=illness_q)
    return trends


def _health_trends_export_query(request):
    """Build extra query string for health-trends CSV exports."""
    from urllib.parse import quote

    parts = []
    term_val = (request.GET.get('term') or '').strip()
    illness_q = (request.GET.get('illness_category') or '').strip()
    if term_val:
        parts.append(f'term={quote(term_val)}')
    if illness_q:
        parts.append(f'illness_category={quote(illness_q)}')
    return f'&{"&".join(parts)}' if parts else ''


def health_trends(request):
    """Student health trend analysis across semesters."""
    date_from, date_to = _get_date_range(request)
    form = HealthTrendFilterForm(
        request.GET or None,
        initial={'date_from': date_from, 'date_to': date_to},
    )
    trends = _filtered_health_trend_records(request)
    illness_q = (request.GET.get('illness_category') or '').strip() if request.GET else ''

    live_illness = _illness_stats(
        date_from, date_to,
        diagnosis_query=illness_q or None,
    )

    live_illness_stats = live_illness[:20]
    context = {
        'form': form,
        'trends': trends,
        'trends_count': trends.count(),
        'live_illness_stats': live_illness_stats,
        'live_cases_total': sum(item['count'] for item in live_illness_stats),
        'illness_filter': illness_q,
        'date_from': date_from,
        'date_to': date_to,
        'period_presets': _period_presets(date_from, date_to),
        'export_query': _health_trends_export_query(request),
    }
    return render(request, 'analytics/health_trends.html', context)


# =====================================================================
# 3. Predictive Analytics
# =====================================================================

@login_required
@role_required('staff', 'doctor', 'admin')
def predictive_analytics(request):
    """View predictive insights & generate new ones."""
    insights = PredictiveInsight.objects.all()

    insight_filter = request.GET.get('type', '')
    if insight_filter:
        insights = insights.filter(insight_type=insight_filter)

    # Generate on-the-fly predictions
    date_from, date_to = _get_date_range(request)
    hourly = _appointment_by_hour(date_from, date_to)
    weekday = _appointment_by_weekday(date_from, date_to)

    # Simple peak hour prediction
    peak_hour = max(hourly, key=lambda x: x['count'])['hour'] if hourly else None
    busiest_day = max(weekday, key=lambda x: x['count'])['weekday'] if weekday else None

    day_names = {1: 'Sunday', 2: 'Monday', 3: 'Tuesday', 4: 'Wednesday',
                 5: 'Thursday', 6: 'Friday', 7: 'Saturday'}

    context = {
        'insights': paginate_queryset(insights, request, per_page=10),
        'insight_types': PredictiveInsight.INSIGHT_TYPES,
        'selected_type': insight_filter,
        'peak_hour': peak_hour,
        'peak_hour_display': f'{peak_hour:02d}:00' if peak_hour is not None else 'N/A',
        'busiest_day': day_names.get(busiest_day, 'N/A'),
        'period_hint': f'{date_from.strftime("%b %d")} – {date_to.strftime("%b %d")}',
        'period_presets': _period_presets(date_from, date_to),
        'hourly_data': hourly,
        'weekday_data': weekday,
        'day_names': day_names,
        'date_from': date_from,
        'date_to': date_to,
    }
    return render(request, 'analytics/predictive_analytics.html', context)


@login_required
@admin_required
def generate_predictive_insight(request):
    """Generate a new predictive insight based on historical data."""
    if request.method != 'POST':
        return redirect('analytics:predictive_analytics')

    insight_type = request.POST.get('insight_type', 'peak_hours')
    date_from, date_to = _get_date_range(request)

    data = {}
    title = ''
    description = ''
    risk_level = 'low'

    if insight_type == 'peak_hours':
        hourly = _appointment_by_hour(date_from, date_to)
        peak = max(hourly, key=lambda x: x['count']) if hourly else {'hour': 0, 'count': 0}
        title = f"Peak Hours Analysis ({date_from} to {date_to})"
        description = f"Highest appointment volume at {peak['hour']}:00 with {peak['count']} appointments."
        data = {'hourly': hourly, 'peak': peak}

    elif insight_type == 'medicine_demand':
        illness = _illness_stats(date_from, date_to)
        title = f"Medicine Demand Forecast ({date_from} to {date_to})"
        top = illness[:5] if illness else []
        top_names = ', '.join([i['diagnosis'] for i in top]) if top else 'None'
        description = f"Top diagnoses driving demand: {top_names}. Plan supplies accordingly."
        data = {'top_diagnoses': illness[:10]}

    elif insight_type == 'staff_workload':
        from appointments.models import Appointment
        staff_load = list(
            Appointment.objects.filter(date__gte=date_from, date__lte=date_to, status='completed')
            .values('doctor__first_name', 'doctor__last_name')
            .annotate(count=Count('id'))
            .order_by('-count')[:10]
        )
        title = f"Staff Workload ({date_from} to {date_to})"
        description = f"Workload distribution across {len(staff_load)} clinicians."
        data = {'staff_load': staff_load}

    elif insight_type == 'outbreak_risk':
        illness = _illness_stats(date_from, date_to)
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
        data = {'illness_stats': illness[:10], 'total_cases': total}

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
    return redirect('analytics:predictive_analytics')


# =====================================================================
# 4. Resource Utilization
# =====================================================================

def _utilization_records_qs(date_from, date_to):
    return ResourceUtilization.objects.filter(date__gte=date_from, date__lte=date_to)


def _resource_utilization_staff_stats(date_from, date_to):
    from appointments.models import Appointment
    return list(
        Appointment.objects.filter(
            date__gte=date_from, date__lte=date_to, status='completed',
        )
        .values('doctor__first_name', 'doctor__last_name')
        .annotate(total=Count('id'))
        .order_by('-total')
    )


def _resource_utilization_kpis(records):
    avg_consultation = records.aggregate(avg=Avg('avg_consultation_minutes'))['avg'] or 0
    total_throughput = records.aggregate(total=Sum('patient_throughput'))['total'] or 0
    avg_throughput = records.aggregate(avg=Avg('patient_throughput'))['avg'] or 0
    return round(avg_consultation, 1), total_throughput, round(avg_throughput, 1)


def _write_resource_utilization_csv(writer, date_from, date_to):
    records = _utilization_records_qs(date_from, date_to)
    avg_consultation, total_throughput, avg_throughput = _resource_utilization_kpis(records)
    staff_stats = _resource_utilization_staff_stats(date_from, date_to)
    staff_total = sum(s['total'] for s in staff_stats)

    writer.writerow(['Resource Utilization'])
    writer.writerow(['Period from', date_from])
    writer.writerow(['Period to', date_to])
    writer.writerow([])
    writer.writerow(['Summary KPIs'])
    writer.writerow(['Metric', 'Value'])
    writer.writerow(['Avg consultation (minutes)', avg_consultation])
    writer.writerow(['Total throughput', total_throughput])
    writer.writerow(['Avg daily throughput', avg_throughput])
    writer.writerow(['Staff completions (appointments)', staff_total])
    writer.writerow([])
    writer.writerow(['Staff completions'])
    writer.writerow(['Staff member', 'Completed appointments'])
    for row in staff_stats:
        name = f"{row['doctor__first_name']} {row['doctor__last_name']}".strip()
        writer.writerow([name, row['total']])
    writer.writerow([])
    writer.writerow(['Daily utilization log'])
    writer.writerow([
        'Date', 'Consultations', 'Avg minutes', 'Throughput',
        'Staff on duty', 'Peak hour', 'Efficiency score', 'Notes',
    ])
    for r in records.order_by('-date'):
        writer.writerow([
            r.date, r.total_consultations, r.avg_consultation_minutes,
            r.patient_throughput, r.staff_on_duty, r.peak_hour or '',
            r.efficiency_score, r.notes,
        ])


@login_required
@role_required('staff', 'doctor', 'admin')
def resource_utilization(request):
    """Resource utilization overview."""
    date_from, date_to = _get_date_range(request)
    records = _utilization_records_qs(date_from, date_to)
    avg_consultation, total_throughput, avg_throughput = _resource_utilization_kpis(records)
    staff_stats = _resource_utilization_staff_stats(date_from, date_to)
    staff_total_completed = sum(s['total'] for s in staff_stats)

    context = {
        'records': paginate_queryset(records, request, per_page=15),
        'avg_consultation': avg_consultation,
        'avg_consultation_display': f'{avg_consultation} min',
        'total_throughput': total_throughput,
        'avg_throughput': avg_throughput,
        'staff_stats': staff_stats,
        'staff_total_completed': staff_total_completed,
        'period_presets': _period_presets(date_from, date_to),
        'period_hint': f'{date_from.strftime("%b %d")} – {date_to.strftime("%b %d")}',
        'date_from': date_from,
        'date_to': date_to,
    }
    return render(request, 'analytics/resource_utilization.html', context)


# =====================================================================
# 5. Compliance & Accreditation Reporting
# =====================================================================

@login_required
@admin_required
def compliance_reports(request):
    """List and manage compliance reports."""
    reports_qs = ComplianceReport.objects.all()
    report_filter = request.GET.get('type', '')
    if report_filter:
        reports_qs = reports_qs.filter(report_type=report_filter)

    type_labels = dict(ComplianceReport.REPORT_TYPES)
    context = {
        'reports': paginate_queryset(reports_qs, request, per_page=10),
        'report_types': ComplianceReport.REPORT_TYPES,
        'selected_type': report_filter,
        'filter_label': type_labels.get(report_filter, 'All types'),
        'reports_total': reports_qs.count(),
        'reports_draft': reports_qs.filter(status='draft').count(),
        'reports_final': reports_qs.filter(status='final').count(),
        'reports_submitted': reports_qs.filter(status='submitted').count(),
    }
    return render(request, 'analytics/compliance_reports.html', context)


@login_required
@admin_required
def generate_compliance_report(request):
    """Generate a new compliance report."""
    if request.method == 'POST':
        form = ComplianceReportForm(request.POST)
        if form.is_valid():
            report = form.save(commit=False)
            report.generated_by = request.user

            # Build report data
            date_from = report.period_start
            date_to = report.period_end
            from appointments.models import Appointment
            from medical_records.models import MedicalRecord

            data = {
                'total_appointments': Appointment.objects.filter(
                    date__gte=date_from, date__lte=date_to
                ).count(),
                'completed_appointments': Appointment.objects.filter(
                    date__gte=date_from, date__lte=date_to, status='completed'
                ).count(),
                'total_records': MedicalRecord.objects.filter(
                    created_at__date__gte=date_from, created_at__date__lte=date_to
                ).count(),
                'total_patients': User.objects.filter(role__in=PATIENT_ROLE_VALUES).count(),
                'total_staff': User.objects.filter(role__in=['staff', 'doctor']).count(),
                'top_diagnoses': _illness_stats(date_from, date_to)[:10],
                'generated_at': timezone.now().isoformat(),
            }
            report.data_json = data
            report.save()
            messages.success(request, f'Compliance report "{report.title}" generated.')
            return redirect('analytics:compliance_reports')
    else:
        form = ComplianceReportForm()

    return render(request, 'analytics/compliance_report_form.html', {'form': form})


@login_required
@admin_required
def compliance_report_detail(request, pk):
    """View compliance report details."""
    report = get_object_or_404(ComplianceReport, pk=pk)
    return render(request, 'analytics/compliance_report_detail.html', {'report': report})


# =====================================================================
# 6. Population Health Dashboard
# =====================================================================

def _population_health_data(date_from, date_to):
    """Shared aggregates for population health view and exports."""
    from core.models import PatientProfile
    from medical_records.models import MedicalRecord
    from appointments.models import Appointment

    demographics = _student_demographics()
    health_by_course = list(
        MedicalRecord.objects.filter(created_at__date__gte=date_from, created_at__date__lte=date_to)
        .values('patient__patient_profile__course')
        .annotate(count=Count('id'))
        .order_by('-count')
    )
    health_by_year = list(
        MedicalRecord.objects.filter(created_at__date__gte=date_from, created_at__date__lte=date_to)
        .values('patient__patient_profile__year_level')
        .annotate(count=Count('id'))
        .order_by('patient__patient_profile__year_level')
    )
    appt_by_course = list(
        Appointment.objects.filter(date__gte=date_from, date__lte=date_to)
        .values('patient__patient_profile__course')
        .annotate(count=Count('id'))
        .order_by('-count')
    )
    blood_types = list(
        PatientProfile.objects.exclude(blood_type='')
        .values('blood_type')
        .annotate(count=Count('id'))
        .order_by('-count')
    )
    records_in_period = sum(item['count'] for item in health_by_course)
    appt_in_period = sum(item['count'] for item in appt_by_course)
    total_patients = sum(g['count'] for g in demographics['gender']) or PatientProfile.objects.count()

    return {
        'demographics': demographics,
        'health_by_course': health_by_course,
        'health_by_year': health_by_year,
        'health_by_course_total': records_in_period,
        'health_by_year_total': sum(item['count'] for item in health_by_year),
        'appt_by_course': appt_by_course,
        'blood_types': blood_types,
        'total_patients': total_patients,
        'records_in_period': records_in_period,
        'appt_in_period': appt_in_period,
    }


def _write_population_summary_csv(writer, date_from, date_to):
    data = _population_health_data(date_from, date_to)
    demo = data['demographics']

    writer.writerow(['Population Health'])
    writer.writerow(['Period from', date_from])
    writer.writerow(['Period to', date_to])
    writer.writerow([])
    writer.writerow(['Summary KPIs'])
    writer.writerow(['Metric', 'Value'])
    writer.writerow(['Registered patients', data['total_patients']])
    writer.writerow(['Medical records in period', data['records_in_period']])
    writer.writerow(['Appointments in period', data['appt_in_period']])
    writer.writerow([])

    def _write_distribution(title, rows, label_key):
        writer.writerow([title])
        writer.writerow(['Category', 'Count'])
        for row in rows:
            writer.writerow([row.get(label_key) or 'Unknown', row['count']])
        writer.writerow([])

    _write_distribution('Gender distribution', demo['gender'], 'gender')
    _write_distribution('Year level distribution', demo['year_level'], 'year_level')
    _write_distribution('Course distribution', demo['course'], 'course')
    _write_distribution('Blood type distribution', data['blood_types'], 'blood_type')
    _write_distribution(
        'Medical records by course (period)',
        [
            {
                'course': item['patient__patient_profile__course'] or 'Unknown',
                'count': item['count'],
            }
            for item in data['health_by_course']
        ],
        'course',
    )
    _write_distribution(
        'Medical records by year level (period)',
        [
            {
                'year_level': item['patient__patient_profile__year_level'] or 'Unknown',
                'count': item['count'],
            }
            for item in data['health_by_year']
        ],
        'year_level',
    )
    _write_distribution(
        'Appointments by course (period)',
        [
            {
                'course': item['patient__patient_profile__course'] or 'Unknown',
                'count': item['count'],
            }
            for item in data['appt_by_course']
        ],
        'course',
    )


def _write_population_period_csv(writer, date_from, date_to):
    data = _population_health_data(date_from, date_to)
    writer.writerow(['Population period activity'])
    writer.writerow(['Period from', date_from])
    writer.writerow(['Period to', date_to])
    writer.writerow([])
    writer.writerow(['Medical records by course'])
    writer.writerow(['Course', 'Count'])
    for item in data['health_by_course']:
        writer.writerow([
            item['patient__patient_profile__course'] or 'Unknown',
            item['count'],
        ])
    writer.writerow([])
    writer.writerow(['Medical records by year level'])
    writer.writerow(['Year level', 'Count'])
    for item in data['health_by_year']:
        writer.writerow([
            item['patient__patient_profile__year_level'] or 'Unknown',
            item['count'],
        ])
    writer.writerow([])
    writer.writerow(['Appointments by course'])
    writer.writerow(['Course', 'Count'])
    for item in data['appt_by_course']:
        writer.writerow([
            item['patient__patient_profile__course'] or 'Unknown',
            item['count'],
        ])


@login_required
@role_required('staff', 'doctor', 'admin')
def population_health(request):
    """Population health dashboard by demographics."""
    date_from, date_to = _get_date_range(request)
    context = _population_health_data(date_from, date_to)
    context.update({
        'period_presets': _period_presets(date_from, date_to),
        'period_hint': f'{date_from.strftime("%b %d")} – {date_to.strftime("%b %d")}',
        'date_from': date_from,
        'date_to': date_to,
    })
    return render(request, 'analytics/population_health.html', context)


# =====================================================================
# 7. Financial & Cost Analysis
# =====================================================================

def _fmt_peso(amount):
    """Format a decimal amount as Philippine peso."""
    value = amount or Decimal('0')
    return f'₱{value:,.2f}'


@login_required
@admin_required
def financial_overview(request):
    """Financial overview dashboard."""
    date_from, date_to = _get_date_range(request)
    summary = _financial_summary(date_from, date_to)
    records_qs = FinancialRecord.objects.filter(
        date__gte=date_from, date__lte=date_to,
    ).order_by('-date', '-id')

    context = {
        'summary': summary,
        'records': paginate_queryset(records_qs, request, per_page=15),
        'records_count': records_qs.count(),
        'date_from': date_from,
        'date_to': date_to,
        'period_presets': _period_presets(date_from, date_to),
        'period_hint': f'{date_from.strftime("%b %d")} – {date_to.strftime("%b %d")}',
        'expenses_display': _fmt_peso(summary['total_expenses']),
        'income_display': _fmt_peso(summary['total_income']),
        'net_display': _fmt_peso(summary['net']),
        'net_variant': 'success' if summary['net'] >= 0 else 'danger',
    }
    return render(request, 'analytics/financial_overview.html', context)


@login_required
@admin_required
def financial_record_create(request):
    """Create a financial record."""
    if request.method == 'POST':
        form = FinancialRecordForm(request.POST)
        if form.is_valid():
            record = form.save(commit=False)
            record.recorded_by = request.user
            record.save()
            messages.success(request, 'Financial record added successfully.')
            return redirect('analytics:financial_overview')
    else:
        form = FinancialRecordForm()
    return render(request, 'analytics/financial_record_form.html', {'form': form})


# =====================================================================
# 8. Academic Integration
# =====================================================================

def _academic_correlation_data(date_from, date_to):
    """Shared aggregates for academic correlation view and exports."""
    from appointments.models import Appointment

    appt_qs = Appointment.objects.filter(date__gte=date_from, date__lte=date_to)
    frequent_visitors = list(
        appt_qs.values(
            'patient__id', 'patient__first_name', 'patient__last_name',
            'patient__email', 'patient__patient_profile__course',
            'patient__patient_profile__year_level',
        )
        .annotate(visit_count=Count('id'))
        .order_by('-visit_count')[:20]
    )
    emergency_visits = list(
        appt_qs.filter(appointment_type='emergency')
        .values('patient__patient_profile__course')
        .annotate(count=Count('id'))
        .order_by('-count')
    )
    high_visit_patients = (
        appt_qs.values('patient')
        .annotate(visit_count=Count('id'))
        .filter(visit_count__gte=5)
        .count()
    )
    return {
        'frequent_visitors': frequent_visitors,
        'emergency_visits': emergency_visits,
        'total_visits': appt_qs.count(),
        'high_visit_patients': high_visit_patients,
        'emergency_total': sum(item['count'] for item in emergency_visits),
    }


def _write_academic_summary_csv(writer, date_from, date_to):
    data = _academic_correlation_data(date_from, date_to)
    writer.writerow(['Academic Correlation'])
    writer.writerow(['Period from', date_from])
    writer.writerow(['Period to', date_to])
    writer.writerow([])
    writer.writerow(['Summary KPIs'])
    writer.writerow(['Metric', 'Value'])
    writer.writerow(['Total visits', data['total_visits']])
    writer.writerow(['Patients with 5+ visits', data['high_visit_patients']])
    writer.writerow(['Emergency visits', data['emergency_total']])
    writer.writerow([])
    writer.writerow(['Frequent clinic visitors'])
    writer.writerow(['Patient', 'Email', 'Course', 'Year level', 'Visits'])
    for row in data['frequent_visitors']:
        name = f"{row['patient__first_name']} {row['patient__last_name']}".strip()
        writer.writerow([
            name,
            row['patient__email'],
            row['patient__patient_profile__course'] or '',
            row['patient__patient_profile__year_level'] or '',
            row['visit_count'],
        ])
    writer.writerow([])
    writer.writerow(['Emergency visits by course'])
    writer.writerow(['Course', 'Count'])
    for row in data['emergency_visits']:
        writer.writerow([
            row['patient__patient_profile__course'] or 'Unknown',
            row['count'],
        ])


def _write_academic_visitors_csv(writer, date_from, date_to):
    data = _academic_correlation_data(date_from, date_to)
    writer.writerow(['Frequent clinic visitors'])
    writer.writerow(['Period from', date_from])
    writer.writerow(['Period to', date_to])
    writer.writerow(['Patient', 'Email', 'Course', 'Year level', 'Visits'])
    for row in data['frequent_visitors']:
        name = f"{row['patient__first_name']} {row['patient__last_name']}".strip()
        writer.writerow([
            name,
            row['patient__email'],
            row['patient__patient_profile__course'] or '',
            row['patient__patient_profile__year_level'] or '',
            row['visit_count'],
        ])


@login_required
@role_required('staff', 'doctor', 'admin')
def academic_correlation(request):
    """Correlate health data with academic indicators (absenteeism)."""
    date_from, date_to = _get_date_range(request)
    context = _academic_correlation_data(date_from, date_to)
    context.update({
        'period_presets': _period_presets(date_from, date_to),
        'period_hint': f'{date_from.strftime("%b %d")} – {date_to.strftime("%b %d")}',
        'date_from': date_from,
        'date_to': date_to,
    })
    return render(request, 'analytics/academic_correlation.html', context)


# =====================================================================
# Export helpers
# =====================================================================

def _write_staff_dashboard_csv(writer, user, date_from, date_to):
    from appointments.models import Appointment

    my_appointments = Appointment.objects.filter(
        doctor=user, date__gte=date_from, date__lte=date_to,
    )
    trend = list(
        my_appointments.values(day=F('date'))
        .annotate(count=Count('id')).order_by('day')
    )
    diagnoses = _illness_stats(date_from, date_to, doctor=user)[:10]
    hourly_series, hourly_peak, _hourly_has_data = _hourly_chart_series(
        _appointment_by_hour(date_from, date_to, doctor=user),
    )

    writer.writerow(['Staff Analytics Dashboard'])
    writer.writerow(['Exported by', user.get_full_name() or user.email])
    writer.writerow(['Period from', date_from])
    writer.writerow(['Period to', date_to])
    writer.writerow([])
    writer.writerow(['Summary KPIs'])
    writer.writerow(['Metric', 'Value'])
    writer.writerow(['Unique patients', my_appointments.values('patient').distinct().count()])
    writer.writerow(['Consultations (completed)', my_appointments.filter(status='completed').count()])
    writer.writerow(['Pending appointments', my_appointments.filter(status='pending').count()])
    writer.writerow([])
    writer.writerow(['Appointment trend'])
    writer.writerow(['Date', 'Appointments'])
    for row in trend:
        writer.writerow([row['day'], row['count']])
    writer.writerow([])
    writer.writerow(['Top diagnoses'])
    writer.writerow(['Diagnosis', 'Count'])
    for row in diagnoses:
        writer.writerow([row['diagnosis'], row['count']])
    writer.writerow([])
    writer.writerow(['Hourly distribution'])
    writer.writerow(['Hour', 'Appointments'])
    for row in hourly_series:
        writer.writerow([row['label'], row['count']])


def _write_health_trends_csv(writer, request, date_from, date_to):
    trends = _filtered_health_trend_records(request)
    illness_q = (request.GET.get('illness_category') or '').strip()
    live_stats = _illness_stats(
        date_from, date_to,
        diagnosis_query=illness_q or None,
    )

    writer.writerow(['Health Trends'])
    writer.writerow(['Period from', date_from])
    writer.writerow(['Period to', date_to])
    if illness_q:
        writer.writerow(['Illness filter', illness_q])
    term_val = (request.GET.get('term') or '').strip()
    if term_val:
        writer.writerow(['School term filter', term_val])
    writer.writerow([])
    writer.writerow(['Summary'])
    writer.writerow(['Metric', 'Value'])
    writer.writerow(['Trend records', trends.count()])
    writer.writerow(['Diagnosis types', len(live_stats)])
    writer.writerow(['Cases in period', sum(item['count'] for item in live_stats)])
    writer.writerow([])
    writer.writerow(['Semester trend records'])
    writer.writerow(['Academic Year', 'Semester', 'Illness', 'Cases', 'Notes'])
    for t in trends.order_by('-academic_year', 'semester', 'illness_category'):
        writer.writerow([
            t.academic_year, t.get_semester_display(),
            t.illness_category, t.case_count, t.notes,
        ])
    writer.writerow([])
    writer.writerow(['Live diagnoses'])
    writer.writerow(['Diagnosis', 'Count'])
    for row in live_stats:
        writer.writerow([row['diagnosis'], row['count']])


def _write_admin_dashboard_csv(writer, date_from, date_to):
    from appointments.models import Appointment
    from medical_records.models import MedicalRecord
    from feedback.models import Feedback

    total_patients = User.objects.filter(role__in=PATIENT_ROLE_VALUES).count()
    total_staff = User.objects.filter(role__in=['staff', 'doctor']).count()
    total_appointments = Appointment.objects.filter(
        date__gte=date_from, date__lte=date_to,
    ).count()
    total_records = MedicalRecord.objects.filter(
        created_at__date__gte=date_from, created_at__date__lte=date_to,
    ).count()
    avg_feedback = Feedback.objects.aggregate(avg=Avg('rating'))['avg'] or 0
    volume = _appointment_volume(date_from, date_to)
    by_type = _appointment_by_type(date_from, date_to)
    diagnoses = _illness_stats(date_from, date_to)[:15]

    writer.writerow(['Clinic Analytics Dashboard'])
    writer.writerow(['Period from', date_from])
    writer.writerow(['Period to', date_to])
    writer.writerow([])
    writer.writerow(['Summary KPIs'])
    writer.writerow(['Metric', 'Value'])
    writer.writerow(['Registered patients', total_patients])
    writer.writerow(['Staff (doctors & staff)', total_staff])
    writer.writerow(['Appointments in period', total_appointments])
    writer.writerow(['Medical records in period', total_records])
    writer.writerow(['Average feedback rating', round(avg_feedback, 1)])
    writer.writerow([])
    writer.writerow(['Appointment volume'])
    writer.writerow(['Date', 'Appointments'])
    for row in volume:
        writer.writerow([row['day'], row['count']])
    writer.writerow([])
    writer.writerow(['Appointment types'])
    writer.writerow(['Type', 'Count'])
    for row in by_type:
        writer.writerow([row['appointment_type'], row['count']])
    writer.writerow([])
    writer.writerow(['Top diagnoses'])
    writer.writerow(['Diagnosis', 'Count'])
    for row in diagnoses:
        writer.writerow([row['diagnosis'], row['count']])


def _financial_category_label(category_key):
    return dict(FinancialRecord.CATEGORY_CHOICES).get(category_key, category_key or 'Unknown')


def _financial_monthly_table(monthly_rows):
    """Pivot monthly aggregates into sorted (month, expenses, income) rows."""
    monthly_data = OrderedDict()
    for row in monthly_rows:
        month = row.get('month')
        key = month.strftime('%Y-%m') if month else ''
        if key not in monthly_data:
            monthly_data[key] = {'expense': Decimal('0'), 'income': Decimal('0')}
        if row['is_expense']:
            monthly_data[key]['expense'] = row['total'] or Decimal('0')
        else:
            monthly_data[key]['income'] = row['total'] or Decimal('0')
    return monthly_data.items()


def _write_financial_summary_csv(writer, date_from, date_to):
    summary = _financial_summary(date_from, date_to)
    records_qs = FinancialRecord.objects.filter(
        date__gte=date_from, date__lte=date_to,
    ).order_by('-date', '-id')

    writer.writerow(['Financial & Cost Analysis'])
    writer.writerow(['Period from', date_from])
    writer.writerow(['Period to', date_to])
    writer.writerow([])
    writer.writerow(['Summary KPIs'])
    writer.writerow(['Metric', 'Amount (PHP)'])
    writer.writerow(['Total expenses', summary['total_expenses']])
    writer.writerow(['Total income', summary['total_income']])
    writer.writerow(['Net', summary['net']])
    writer.writerow([])
    writer.writerow(['Expenses by category'])
    writer.writerow(['Category', 'Amount (PHP)'])
    for row in summary['by_category']:
        writer.writerow([
            _financial_category_label(row['category']),
            row['total'],
        ])
    writer.writerow([])
    writer.writerow(['Monthly overview'])
    writer.writerow(['Month', 'Expenses (PHP)', 'Income (PHP)'])
    for month, totals in _financial_monthly_table(summary['monthly']):
        writer.writerow([month, totals['expense'], totals['income']])
    writer.writerow([])
    writer.writerow(['Financial records'])
    writer.writerow(['Date', 'Category', 'Description', 'Amount (PHP)', 'Type', 'Reference'])
    for record in records_qs:
        writer.writerow([
            record.date,
            record.get_category_display(),
            record.description,
            record.amount,
            'Expense' if record.is_expense else 'Income',
            record.reference_number,
        ])


@login_required
@role_required('staff', 'doctor', 'admin')
def export_report(request):
    """Export analytics data as CSV or Excel-compatible CSV."""
    report_type = request.GET.get('report', 'appointments')
    date_from, date_to = _get_date_range(request)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = (
        f'attachment; filename="analytics_{report_type}_{date_from}_to_{date_to}.csv"'
    )
    writer = csv.writer(response)

    if report_type == 'staff_dashboard':
        if request.user.role not in ('staff', 'doctor'):
            return HttpResponseForbidden()
        _write_staff_dashboard_csv(writer, request.user, date_from, date_to)

    elif report_type == 'admin_dashboard':
        if request.user.role != 'admin':
            return HttpResponseForbidden()
        _write_admin_dashboard_csv(writer, date_from, date_to)

    elif report_type == 'my_appointments':
        if request.user.role not in ('staff', 'doctor'):
            return HttpResponseForbidden()
        from appointments.models import Appointment
        writer.writerow(['Date', 'Time', 'Patient', 'Type', 'Status', 'Notes'])
        qs = Appointment.objects.filter(
            doctor=request.user,
            date__gte=date_from,
            date__lte=date_to,
        ).select_related('patient').order_by('date', 'time')
        for a in qs:
            writer.writerow([
                a.date, a.time,
                a.patient.get_full_name() if a.patient else '',
                a.get_appointment_type_display(),
                a.get_status_display(),
                getattr(a, 'notes', '') or '',
            ])

    elif report_type == 'appointments':
        from appointments.models import Appointment
        writer.writerow(['Date', 'Time', 'Patient', 'Doctor', 'Type', 'Status'])
        for a in Appointment.objects.filter(date__gte=date_from, date__lte=date_to).select_related('patient', 'doctor').order_by('date', 'time'):
            writer.writerow([
                a.date, a.time,
                a.patient.get_full_name() if a.patient else '',
                a.doctor.get_full_name() if a.doctor else '',
                a.get_appointment_type_display(),
                a.get_status_display(),
            ])

    elif report_type == 'medical_records':
        from medical_records.models import MedicalRecord
        writer.writerow(['Date', 'Patient', 'Doctor', 'Diagnosis', 'Treatment'])
        for r in MedicalRecord.objects.filter(created_at__date__gte=date_from, created_at__date__lte=date_to).select_related('patient', 'doctor').order_by('-created_at'):
            writer.writerow([
                r.created_at.strftime('%Y-%m-%d'),
                r.patient.get_full_name() if r.patient else '',
                r.doctor.get_full_name() if r.doctor else '',
                r.diagnosis, r.treatment,
            ])

    elif report_type in ('financial', 'financial_summary'):
        if request.user.role != 'admin':
            return HttpResponseForbidden()
        if report_type == 'financial_summary':
            _write_financial_summary_csv(writer, date_from, date_to)
        else:
            writer.writerow(['Date', 'Category', 'Description', 'Amount (PHP)', 'Type', 'Reference'])
            for f in FinancialRecord.objects.filter(
                date__gte=date_from, date__lte=date_to,
            ).order_by('-date', '-id'):
                writer.writerow([
                    f.date, f.get_category_display(), f.description,
                    f.amount, 'Expense' if f.is_expense else 'Income',
                    f.reference_number,
                ])

    elif report_type == 'health_trends':
        writer.writerow(['Academic Year', 'Semester', 'Illness', 'Cases', 'Notes'])
        for t in _filtered_health_trend_records(request).order_by(
            '-academic_year', 'semester', 'illness_category',
        ):
            writer.writerow([
                t.academic_year, t.get_semester_display(),
                t.illness_category, t.case_count, t.notes,
            ])

    elif report_type == 'health_trends_live':
        illness_q = (request.GET.get('illness_category') or '').strip()
        writer.writerow(['Diagnosis', 'Count'])
        for row in _illness_stats(
            date_from, date_to,
            diagnosis_query=illness_q or None,
        ):
            writer.writerow([row['diagnosis'], row['count']])

    elif report_type == 'health_trends_summary':
        _write_health_trends_csv(writer, request, date_from, date_to)

    elif report_type == 'resource_utilization_summary':
        _write_resource_utilization_csv(writer, date_from, date_to)

    elif report_type == 'resource_utilization_daily':
        writer.writerow([
            'Date', 'Consultations', 'Avg minutes', 'Throughput',
            'Staff on duty', 'Peak hour', 'Efficiency score', 'Notes',
        ])
        for r in _utilization_records_qs(date_from, date_to).order_by('-date'):
            writer.writerow([
                r.date, r.total_consultations, r.avg_consultation_minutes,
                r.patient_throughput, r.staff_on_duty, r.peak_hour or '',
                r.efficiency_score, r.notes,
            ])

    elif report_type == 'resource_utilization_staff':
        writer.writerow(['Staff member', 'Completed appointments'])
        for row in _resource_utilization_staff_stats(date_from, date_to):
            name = f"{row['doctor__first_name']} {row['doctor__last_name']}".strip()
            writer.writerow([name, row['total']])

    elif report_type == 'population_summary':
        _write_population_summary_csv(writer, date_from, date_to)

    elif report_type == 'population_period':
        _write_population_period_csv(writer, date_from, date_to)

    elif report_type == 'academic_summary':
        _write_academic_summary_csv(writer, date_from, date_to)

    elif report_type == 'academic_visitors':
        _write_academic_visitors_csv(writer, date_from, date_to)

    elif report_type == 'academic_emergency':
        writer.writerow(['Emergency visits by course'])
        writer.writerow(['Period from', date_from])
        writer.writerow(['Period to', date_to])
        writer.writerow(['Course', 'Count'])
        for row in _academic_correlation_data(date_from, date_to)['emergency_visits']:
            writer.writerow([
                row['patient__patient_profile__course'] or 'Unknown',
                row['count'],
            ])

    elif report_type == 'demographics':
        from core.models import PatientProfile
        writer.writerow(['Patient ID', 'Course', 'Year Level', 'Gender', 'Blood Type'])
        for p in PatientProfile.objects.select_related('user').order_by('patient_id'):
            writer.writerow([
                p.patient_id, p.course, p.year_level, p.gender, p.blood_type,
            ])

    # Log the export
    ExportLog.objects.create(
        report_name=report_type,
        export_format='csv',
        exported_by=request.user,
    )

    return response


# =====================================================================
# API endpoints for chart data (JSON)
# =====================================================================

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
def chart_data_api(request):
    """Return JSON chart data for AJAX requests on the dashboard."""
    chart = request.GET.get('chart', '')
    date_from, date_to = _get_date_range(request)

    data = {}

    if chart == 'appointment_volume':
        raw = _appointment_volume(date_from, date_to)
        data = {
            'labels': [r['day'].strftime('%Y-%m-%d') for r in raw],
            'values': [r['count'] for r in raw],
        }

    elif chart == 'appointment_by_type':
        raw = _appointment_by_type(date_from, date_to)
        data = {
            'labels': [r['appointment_type'] for r in raw],
            'values': [r['count'] for r in raw],
        }

    elif chart == 'hourly_distribution':
        raw = _appointment_by_hour(date_from, date_to)
        data = {
            'labels': [f"{r['hour']}:00" for r in raw],
            'values': [r['count'] for r in raw],
        }

    elif chart == 'illness_stats':
        raw = _illness_stats(date_from, date_to)[:15]
        data = {
            'labels': [r['diagnosis'] for r in raw],
            'values': [r['count'] for r in raw],
        }

    elif chart == 'demographics_course':
        demo = _student_demographics()
        data = {
            'labels': [r['course'] for r in demo['course']],
            'values': [r['count'] for r in demo['course']],
        }

    elif chart == 'demographics_year':
        demo = _student_demographics()
        data = {
            'labels': [r['year_level'] for r in demo['year_level']],
            'values': [r['count'] for r in demo['year_level']],
        }

    elif chart == 'financial_category':
        raw = _financial_summary(date_from, date_to)['by_category']
        data = {
            'labels': [r['category'] for r in raw],
            'values': [float(r['total']) for r in raw],
        }

    return JsonResponse(data)
