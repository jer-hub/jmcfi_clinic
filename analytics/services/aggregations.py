"""Analytics aggregation helpers shared by views and exports."""

from collections import defaultdict, OrderedDict
from datetime import timedelta
from decimal import Decimal

from django.db import models
from django.db.models import Avg, Count, F, Sum
from django.db.models.functions import (
    Cast, ExtractHour, ExtractWeekDay, TruncMonth,
)
from django.utils import timezone

from core.utils import parse_date

from analytics.academic_filters import (
    apply_academic_filters,
    apply_concern_academic_filters,
    apply_dental_academic_filters,
    apply_patient_chart_academic_filters,
    academic_filters_active,
    get_academic_filters,
    period_presets as _period_presets,
)
from analytics.models import (
    ComplianceReport, FinancialRecord, HealthTrendRecord, ResourceUtilization,
)


def filters_from_request(request):
    return get_academic_filters(request)


def get_date_range(request):
    """Extract date_from / date_to from GET/POST params with sensible defaults."""
    params = request.POST if request.method == 'POST' and request.POST else request.GET
    date_from = parse_date(params.get('date_from'))
    date_to = parse_date(params.get('date_to'))
    if not date_to:
        date_to = timezone.now().date()
    if not date_from:
        date_from = date_to - timedelta(days=90)
    return date_from, date_to


def period_presets_for_request(request, date_from, date_to):
    return _period_presets(date_from, date_to, request)


def friendly_diagnosis_label(value):
    """Normalize diagnosis labels for chart/list display."""
    text = (value or '').strip()
    if not text:
        return 'Unspecified diagnosis'
    text = ' '.join(text.replace('_', ' ').split())
    if text.islower():
        return text.title()
    return text


def diagnosis_aggregate_key(value):
    """Bucket placeholder diagnoses so lists stay readable."""
    text = friendly_diagnosis_label(value)
    key = text.lower().strip('.')
    if key in {'diagnosis', 'diag', 'unspecified diagnosis', 'n/a', 'na', 'none', 'test'}:
        return '__unspecified__'
    if len(key) <= 12 and key.startswith('diag'):
        return '__unspecified__'
    return key


def diagnosis_display_name(key, sample_value):
    if key == '__unspecified__':
        return 'Unspecified / general'
    return friendly_diagnosis_label(sample_value)


def student_visit_history(user, months=6):
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


def illness_stats(date_from, date_to, doctor=None, diagnosis_query=None, filters=None):
    """Aggregate diagnosis signals from medical records plus dental encounters."""
    from medical_records.models import MedicalRecord
    from dental_records.models import DentalRecord

    filters = filters or {}
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

    medical_qs = apply_academic_filters(medical_qs, filters)
    dental_qs = apply_dental_academic_filters(dental_qs, filters)

    aggregated = defaultdict(int)
    display_names = {}

    for item in medical_qs.values('diagnosis').annotate(count=Count('id')):
        key = diagnosis_aggregate_key(item['diagnosis'])
        aggregated[key] += item['count']
        if key not in display_names:
            display_names[key] = diagnosis_display_name(key, item['diagnosis'])

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


def illness_source_counts(date_from, date_to, diagnosis_query=None, filters=None):
    """Medical vs dental case counts matching live diagnosis filters."""
    from medical_records.models import MedicalRecord
    from dental_records.models import DentalRecord

    filters = filters or {}
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
    medical_qs = apply_academic_filters(medical_qs, filters)
    dental_qs = apply_dental_academic_filters(dental_qs, filters)
    dental_count = dental_qs.count()
    if diagnosis_query and 'dental' not in diagnosis_query.lower():
        dental_count = 0
    return medical_qs.count(), dental_count


def appointment_volume(date_from, date_to, filters=None):
    """Appointment counts grouped by date."""
    from appointments.models import Appointment
    qs = Appointment.objects.filter(date__gte=date_from, date__lte=date_to)
    qs = apply_academic_filters(qs, filters or {})
    return list(
        qs.values(day=F('date'))
        .annotate(count=Count('id'))
        .order_by('day')
    )


def appointment_by_type(date_from, date_to, filters=None):
    from appointments.models import Appointment
    qs = Appointment.objects.filter(date__gte=date_from, date__lte=date_to)
    qs = apply_academic_filters(qs, filters or {})
    return list(
        qs.values('appointment_type')
        .annotate(count=Count('id'))
        .order_by('-count')
    )


def appointment_by_hour(date_from, date_to, doctor=None, filters=None):
    from appointments.models import Appointment
    qs = Appointment.objects.filter(date__gte=date_from, date__lte=date_to)
    if doctor is not None:
        qs = qs.filter(doctor=doctor)
    qs = apply_academic_filters(qs, filters or {})
    return list(
        qs.annotate(hour=ExtractHour('time'))
        .values('hour')
        .annotate(count=Count('id'))
        .order_by('hour')
    )


def hourly_chart_series(hourly_rows):
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


def appointment_by_weekday(date_from, date_to, filters=None):
    from appointments.models import Appointment
    qs = Appointment.objects.filter(date__gte=date_from, date__lte=date_to)
    qs = apply_academic_filters(qs, filters or {})
    return list(
        qs.annotate(weekday=ExtractWeekDay('date'))
        .values('weekday')
        .annotate(count=Count('id'))
        .order_by('weekday')
    )


def student_demographics(filters=None):
    """Demographics breakdown from PatientProfile."""
    from core.models import PatientProfile

    profile_qs = PatientProfile.objects.all()
    filters = filters or {}
    if filters.get('department'):
        profile_qs = profile_qs.filter(department=filters['department'])
    if filters.get('course'):
        profile_qs = profile_qs.filter(course=filters['course'])
    if filters.get('year_level'):
        profile_qs = profile_qs.filter(year_level=filters['year_level'])

    course = list(
        profile_qs.exclude(course='').values('course')
        .annotate(count=Count('id')).order_by('-count')
    )
    year_level = list(
        profile_qs.exclude(year_level='').values('year_level')
        .annotate(count=Count('id')).order_by('year_level')
    )
    gender = list(
        profile_qs.exclude(gender='').values('gender')
        .annotate(count=Count('id')).order_by('-count')
    )
    department = list(
        profile_qs.exclude(department='').values('department')
        .annotate(count=Count('id')).order_by('-count')
    )
    return {
        'course': course,
        'year_level': year_level,
        'gender': gender,
        'department': department,
    }


def financial_summary(date_from, date_to):
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


def fmt_peso(amount):
    """Format a decimal amount as Philippine peso."""
    value = amount or Decimal('0')
    return f'₱{value:,.2f}'


def financial_category_label(category_key):
    return dict(FinancialRecord.CATEGORY_CHOICES).get(category_key, category_key or 'Unknown')


def financial_monthly_table(monthly_rows):
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


def filtered_health_trend_records(request):
    """Return HealthTrendRecord queryset matching health-trends page filters."""
    trends = HealthTrendRecord.objects.all()
    illness_q = (request.GET.get('illness_category') or '').strip()
    if illness_q:
        trends = trends.filter(illness_category__icontains=illness_q)
    return trends


def health_trends_export_query(request):
    """Build extra query string for health-trends CSV exports."""
    from urllib.parse import quote
    from analytics.academic_filters import academic_filter_query_string

    parts = []
    illness_q = (request.GET.get('illness_category') or '').strip()
    if illness_q:
        parts.append(f'illness_category={quote(illness_q)}')
    academic_q = academic_filter_query_string(filters_from_request(request))
    if academic_q:
        parts.append(academic_q.lstrip('&'))
    return f'&{"&".join(parts)}' if parts else ''


def utilization_records_qs(date_from, date_to):
    return ResourceUtilization.objects.filter(date__gte=date_from, date__lte=date_to)


def resource_utilization_staff_stats(date_from, date_to, filters=None):
    from appointments.models import Appointment
    qs = Appointment.objects.filter(
        date__gte=date_from, date__lte=date_to, status='completed',
    )
    qs = apply_academic_filters(qs, filters or {})
    return list(
        qs.values('doctor__first_name', 'doctor__last_name')
        .annotate(total=Count('id'))
        .order_by('-total')
    )


def resource_utilization_kpis(records):
    avg_consultation = records.aggregate(avg=Avg('avg_consultation_minutes'))['avg'] or 0
    total_throughput = records.aggregate(total=Sum('patient_throughput'))['total'] or 0
    avg_throughput = records.aggregate(avg=Avg('patient_throughput'))['avg'] or 0
    return round(avg_consultation, 1), total_throughput, round(avg_throughput, 1)


def filtered_compliance_reports(request):
    reports_qs = ComplianceReport.objects.all()
    report_filter = request.GET.get('type', '')
    if report_filter:
        reports_qs = reports_qs.filter(report_type=report_filter)
    filters = filters_from_request(request)
    if academic_filters_active(filters):
        if filters.get('department'):
            reports_qs = reports_qs.filter(
                data_json__academic_filters__department=filters['department'],
            )
        if filters.get('course'):
            reports_qs = reports_qs.filter(
                data_json__academic_filters__course=filters['course'],
            )
        if filters.get('year_level'):
            reports_qs = reports_qs.filter(
                data_json__academic_filters__year_level=filters['year_level'],
            )
    return reports_qs, report_filter, filters


def population_health_data(date_from, date_to, filters=None):
    """Shared aggregates for population health view and exports."""
    from core.models import PatientProfile
    from medical_records.models import MedicalRecord
    from appointments.models import Appointment

    filters = filters or {}
    demographics = student_demographics(filters=filters)

    mr_qs = apply_academic_filters(
        MedicalRecord.objects.filter(
            created_at__date__gte=date_from, created_at__date__lte=date_to,
        ),
        filters,
    )
    appt_qs = apply_academic_filters(
        Appointment.objects.filter(date__gte=date_from, date__lte=date_to),
        filters,
    )

    health_by_department = list(
        mr_qs.values('patient__patient_profile__department')
        .annotate(count=Count('id'))
        .order_by('-count')
    )
    health_by_course = list(
        mr_qs.values('patient__patient_profile__course')
        .annotate(count=Count('id'))
        .order_by('-count')
    )
    health_by_year = list(
        mr_qs.values('patient__patient_profile__year_level')
        .annotate(count=Count('id'))
        .order_by('patient__patient_profile__year_level')
    )
    appt_by_department = list(
        appt_qs.values('patient__patient_profile__department')
        .annotate(count=Count('id'))
        .order_by('-count')
    )
    appt_by_course = list(
        appt_qs.values('patient__patient_profile__course')
        .annotate(count=Count('id'))
        .order_by('-count')
    )
    appt_by_year = list(
        appt_qs.values('patient__patient_profile__year_level')
        .annotate(count=Count('id'))
        .order_by('patient__patient_profile__year_level')
    )

    profile_qs = PatientProfile.objects.all()
    if filters.get('department'):
        profile_qs = profile_qs.filter(department=filters['department'])
    if filters.get('course'):
        profile_qs = profile_qs.filter(course=filters['course'])
    if filters.get('year_level'):
        profile_qs = profile_qs.filter(year_level=filters['year_level'])

    blood_types = list(
        profile_qs.exclude(blood_type='')
        .values('blood_type')
        .annotate(count=Count('id'))
        .order_by('-count')
    )
    records_in_period = mr_qs.count()
    appt_in_period = appt_qs.count()
    total_patients = profile_qs.count() or sum(g['count'] for g in demographics['gender'])

    return {
        'demographics': demographics,
        'health_by_department': health_by_department,
        'health_by_course': health_by_course,
        'health_by_year': health_by_year,
        'health_by_course_total': records_in_period,
        'health_by_year_total': sum(item['count'] for item in health_by_year),
        'appt_by_department': appt_by_department,
        'appt_by_course': appt_by_course,
        'appt_by_year': appt_by_year,
        'blood_types': blood_types,
        'total_patients': total_patients,
        'records_in_period': records_in_period,
        'appt_in_period': appt_in_period,
    }


def academic_correlation_data(date_from, date_to, filters=None):
    """Shared aggregates for academic correlation view and exports."""
    from appointments.models import Appointment

    filters = filters or {}
    appt_qs = apply_academic_filters(
        Appointment.objects.filter(date__gte=date_from, date__lte=date_to),
        filters,
    )
    frequent_visitors = list(
        appt_qs.values(
            'patient__id', 'patient__first_name', 'patient__last_name',
            'patient__email', 'patient__patient_profile__department',
            'patient__patient_profile__course',
            'patient__patient_profile__year_level',
        )
        .annotate(visit_count=Count('id'))
        .order_by('-visit_count')[:20]
    )
    emergency_qs = appt_qs.filter(appointment_type='emergency')
    emergency_visits = list(
        emergency_qs.values('patient__patient_profile__course')
        .annotate(count=Count('id'))
        .order_by('-count')
    )
    emergency_by_department = list(
        emergency_qs.values('patient__patient_profile__department')
        .annotate(count=Count('id'))
        .order_by('-count')
    )
    emergency_by_year = list(
        emergency_qs.values('patient__patient_profile__year_level')
        .annotate(count=Count('id'))
        .order_by('patient__patient_profile__year_level')
    )
    visits_by_department = list(
        appt_qs.values('patient__patient_profile__department')
        .annotate(count=Count('id'))
        .order_by('-count')[:5]
    )
    visits_by_course = list(
        appt_qs.values('patient__patient_profile__course')
        .annotate(count=Count('id'))
        .order_by('-count')[:8]
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
        'emergency_by_department': emergency_by_department,
        'emergency_by_year': emergency_by_year,
        'visits_by_department': visits_by_department,
        'visits_by_course': visits_by_course,
        'total_visits': appt_qs.count(),
        'high_visit_patients': high_visit_patients,
        'emergency_total': sum(item['count'] for item in emergency_visits),
    }


def filtered_concern_records(date_from, date_to, filters=None, search=None):
    """Concern logs in range with optional academic and text search filters."""
    from manage_concern.models import ConcernRecord

    qs = ConcernRecord.objects.filter(
        date__gte=date_from,
        date__lte=date_to,
    ).select_related(
        'college_department',
        'course_program',
        'year_level',
        'patient_user',
        'created_by',
    )
    if filters:
        qs = apply_concern_academic_filters(qs, filters)
    q = (search or '').strip()
    if q:
        from django.db.models import Q

        qs = qs.filter(
            Q(concerns__icontains=q)
            | Q(management_treatment__icontains=q)
            | Q(disposition__icontains=q)
            | Q(first_name__icontains=q)
            | Q(last_name__icontains=q)
            | Q(department_other__icontains=q)
        )
    return qs


def concern_kpis(date_from, date_to, filters=None, search=None):
    from manage_concern.models import ConcernRecord

    qs = filtered_concern_records(date_from, date_to, filters=filters, search=search)
    total = qs.count()
    unique_patients = qs.exclude(patient_user__isnull=True).values('patient_user').distinct().count()
    catalog_count = qs.filter(affiliation_type=ConcernRecord.AffiliationType.CATALOG).count()
    non_catalog_count = total - catalog_count
    departments_touched = len(
        concern_by_department(date_from, date_to, filters=filters, search=search, limit=500)
    )
    return {
        'total_records': total,
        'unique_patients': unique_patients,
        'catalog_count': catalog_count,
        'non_catalog_count': non_catalog_count,
        'departments_touched': departments_touched,
    }


def concern_volume_by_day(date_from, date_to, filters=None, search=None):
    qs = filtered_concern_records(date_from, date_to, filters=filters, search=search)
    return list(
        qs.values(day=F('date'))
        .annotate(count=Count('id'))
        .order_by('day')
    )


def concern_by_affiliation(date_from, date_to, filters=None, search=None, limit=10):
    from manage_concern.models import ConcernRecord

    qs = filtered_concern_records(date_from, date_to, filters=filters, search=search)
    rows = (
        qs.values('affiliation_type')
        .annotate(count=Count('id'))
        .order_by('-count')
    )
    label_map = dict(ConcernRecord.AffiliationType.choices)
    return [
        {
            'label': label_map.get(row['affiliation_type'], row['affiliation_type'] or 'Unknown'),
            'count': row['count'],
        }
        for row in rows[:limit]
    ]


def concern_by_department(date_from, date_to, filters=None, search=None, limit=15):
    qs = filtered_concern_records(date_from, date_to, filters=filters, search=search)
    by_college = (
        qs.exclude(college_department__isnull=True)
        .values('college_department__name')
        .annotate(count=Count('id'))
        .order_by('-count')
    )
    by_other = (
        qs.filter(college_department__isnull=True)
        .exclude(department_other='')
        .values('department_other')
        .annotate(count=Count('id'))
        .order_by('-count')
    )
    merged = defaultdict(int)
    for row in by_college:
        merged[row['college_department__name'] or 'Unknown'] += row['count']
    for row in by_other:
        merged[row['department_other'] or 'Unknown'] += row['count']
    ranked = sorted(merged.items(), key=lambda item: item[1], reverse=True)
    return [{'label': label, 'count': count} for label, count in ranked[:limit]]


def filtered_patient_charts(date_from, date_to, filters=None, search=None, status=None):
    """Patient charts created in range with optional academic/status/search filters."""
    from health_forms_services.models import PatientChart

    qs = PatientChart.objects.filter(
        created_at__date__gte=date_from,
        created_at__date__lte=date_to,
    ).select_related('user', 'user__patient_profile', 'reviewed_by')
    if filters:
        qs = apply_patient_chart_academic_filters(qs, filters)
    if status:
        qs = qs.filter(status=status)
    q = (search or '').strip()
    if q:
        from django.db.models import Q

        qs = qs.filter(
            Q(first_name__icontains=q)
            | Q(last_name__icontains=q)
            | Q(middle_name__icontains=q)
            | Q(department_college_office__icontains=q)
            | Q(entries__findings__icontains=q)
            | Q(entries__doctors_orders__icontains=q)
        ).distinct()
    return qs


def filtered_patient_chart_entries(date_from, date_to, filters=None, search=None, status=None):
    """Consultation entries in range (by date_and_time) with chart-level filters."""
    from health_forms_services.models import PatientChartEntry

    qs = PatientChartEntry.objects.filter(
        date_and_time__date__gte=date_from,
        date_and_time__date__lte=date_to,
    ).select_related(
        'patient_chart',
        'patient_chart__user',
        'patient_chart__user__patient_profile',
        'recorded_by',
    )
    if filters:
        qs = apply_patient_chart_academic_filters(qs, filters, prefix='patient_chart__')
    if status:
        qs = qs.filter(patient_chart__status=status)
    q = (search or '').strip()
    if q:
        from django.db.models import Q

        qs = qs.filter(
            Q(findings__icontains=q)
            | Q(doctors_orders__icontains=q)
            | Q(patient_chart__first_name__icontains=q)
            | Q(patient_chart__last_name__icontains=q)
            | Q(patient_chart__department_college_office__icontains=q)
        )
    return qs


def patient_chart_kpis(date_from, date_to, filters=None, search=None, status=None):
    from health_forms_services.models import PatientChart

    qs = filtered_patient_charts(
        date_from, date_to, filters=filters, search=search, status=status,
    )
    total = qs.count()
    unique_patients = qs.values('user').distinct().count()
    pending_count = qs.filter(status=PatientChart.Status.PENDING).count()
    completed_count = qs.filter(status=PatientChart.Status.COMPLETED).count()
    entry_count = filtered_patient_chart_entries(
        date_from, date_to, filters=filters, search=search, status=status,
    ).count()
    departments_touched = len(
        patient_chart_by_department(
            date_from, date_to, filters=filters, search=search, status=status, limit=500,
        )
    )
    return {
        'total_charts': total,
        'unique_patients': unique_patients,
        'pending_count': pending_count,
        'completed_count': completed_count,
        'entry_count': entry_count,
        'departments_touched': departments_touched,
    }


def patient_chart_by_status(date_from, date_to, filters=None, search=None, status=None, limit=10):
    from health_forms_services.models import PatientChart

    qs = filtered_patient_charts(
        date_from, date_to, filters=filters, search=search, status=status,
    )
    rows = qs.values('status').annotate(count=Count('id')).order_by('-count')
    label_map = dict(PatientChart.Status.choices)
    return [
        {
            'label': label_map.get(row['status'], row['status'] or 'Unknown'),
            'count': row['count'],
        }
        for row in rows[:limit]
    ]


def patient_chart_by_designation(date_from, date_to, filters=None, search=None, status=None, limit=10):
    from health_forms_services.models import PatientChart

    qs = filtered_patient_charts(
        date_from, date_to, filters=filters, search=search, status=status,
    )
    rows = qs.values('designation').annotate(count=Count('id')).order_by('-count')
    label_map = dict(PatientChart.Designation.choices)
    return [
        {
            'label': label_map.get(row['designation'], row['designation'] or 'Unknown'),
            'count': row['count'],
        }
        for row in rows[:limit]
    ]


def patient_chart_by_department(date_from, date_to, filters=None, search=None, status=None, limit=15):
    qs = filtered_patient_charts(
        date_from, date_to, filters=filters, search=search, status=status,
    )
    rows = (
        qs.exclude(department_college_office='')
        .values('department_college_office')
        .annotate(count=Count('id'))
        .order_by('-count')[:limit]
    )
    return [
        {
            'label': row['department_college_office'] or 'Unknown',
            'count': row['count'],
        }
        for row in rows
    ]


def patient_chart_entry_volume_by_day(date_from, date_to, filters=None, search=None, status=None):
    from django.db.models.functions import TruncDate

    qs = filtered_patient_chart_entries(
        date_from, date_to, filters=filters, search=search, status=status,
    )
    return list(
        qs.annotate(day=TruncDate('date_and_time'))
        .values('day')
        .annotate(count=Count('id'))
        .order_by('day')
    )
