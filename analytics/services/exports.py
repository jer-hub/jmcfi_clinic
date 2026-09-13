"""CSV export writers for analytics reports."""

from django.contrib.auth import get_user_model
from django.db.models import Avg, Count, F

from core.roles import PATIENT_ROLE_VALUES

from analytics.academic_filters import (
    apply_academic_filters,
    write_academic_filter_csv_rows,
)
from analytics.models import FinancialRecord, PredictiveInsight
from analytics.services.aggregations import (
    academic_correlation_data,
    appointment_by_hour,
    appointment_by_type,
    appointment_by_weekday,
    appointment_volume,
    filtered_compliance_reports,
    filtered_health_trend_records,
    filters_from_request,
    financial_category_label,
    financial_monthly_table,
    financial_summary,
    hourly_chart_series,
    illness_stats,
    population_health_data,
    resource_utilization_kpis,
    resource_utilization_staff_stats,
    student_demographics,
    utilization_records_qs,
)

User = get_user_model()


def write_resource_utilization_csv(writer, date_from, date_to, filters=None):
    filters = filters or {}
    records = utilization_records_qs(date_from, date_to)
    avg_consultation, total_throughput, avg_throughput = resource_utilization_kpis(records)
    staff_stats = resource_utilization_staff_stats(date_from, date_to, filters=filters)
    staff_total = sum(s['total'] for s in staff_stats)

    writer.writerow(['Resource Utilization'])
    writer.writerow(['Period from', date_from])
    writer.writerow(['Period to', date_to])
    write_academic_filter_csv_rows(writer, filters)
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


def write_compliance_index_csv(writer, request, date_from, date_to, filters):
    reports_qs, report_filter, _filters = filtered_compliance_reports(request)
    writer.writerow(['Compliance reports index'])
    writer.writerow(['Period from', date_from])
    writer.writerow(['Period to', date_to])
    write_academic_filter_csv_rows(writer, filters or {})
    if report_filter:
        writer.writerow(['Report type', report_filter])
        writer.writerow([])
    writer.writerow([
        'Title', 'Type', 'Status', 'Period start', 'Period end',
        'Department', 'Program', 'Year level', 'Created',
    ])
    for report in reports_qs.order_by('-created_at'):
        stored = (report.data_json or {}).get('academic_filters') or {}
        writer.writerow([
            report.title,
            report.get_report_type_display(),
            report.get_status_display(),
            report.period_start,
            report.period_end,
            stored.get('department') or '',
            stored.get('course') or '',
            stored.get('year_level') or '',
            report.created_at.strftime('%Y-%m-%d %H:%M'),
        ])


def write_predictive_csv(writer, request, date_from, date_to, filters, report_type):
    insight_filter = (request.GET.get('type') or '').strip()
    write_academic_filter_csv_rows(writer, filters or {})
    if report_type == 'predictive_insights':
        insights = PredictiveInsight.objects.all()
        if insight_filter:
            insights = insights.filter(insight_type=insight_filter)
        writer.writerow(['Predictive insights'])
        writer.writerow(['Period from', date_from])
        writer.writerow(['Period to', date_to])
        if insight_filter:
            writer.writerow(['Insight type', insight_filter])
        writer.writerow([])
        writer.writerow(['Title', 'Type', 'Risk', 'Period start', 'Period end', 'Description'])
        for insight in insights.order_by('-created_at'):
            writer.writerow([
                insight.title,
                insight.get_insight_type_display(),
                insight.get_risk_level_display(),
                insight.period_start,
                insight.period_end,
                insight.description,
            ])
        return

    hourly = appointment_by_hour(date_from, date_to, filters=filters)
    weekday = appointment_by_weekday(date_from, date_to, filters=filters)
    day_names = {
        1: 'Sunday', 2: 'Monday', 3: 'Tuesday', 4: 'Wednesday',
        5: 'Thursday', 6: 'Friday', 7: 'Saturday',
    }
    writer.writerow(['Predictive hourly and weekday summary'])
    writer.writerow(['Period from', date_from])
    writer.writerow(['Period to', date_to])
    writer.writerow([])
    writer.writerow(['Hourly distribution'])
    writer.writerow(['Hour', 'Appointments'])
    for row in hourly:
        writer.writerow([f"{row['hour']:02d}:00", row['count']])
    writer.writerow([])
    writer.writerow(['Day of week'])
    writer.writerow(['Weekday', 'Appointments'])
    for row in weekday:
        writer.writerow([day_names.get(row['weekday'], row['weekday']), row['count']])


def write_population_summary_csv(writer, date_from, date_to, filters=None):
    data = population_health_data(date_from, date_to, filters=filters)
    demo = data['demographics']

    writer.writerow(['Population Health'])
    writer.writerow(['Period from', date_from])
    writer.writerow(['Period to', date_to])
    write_academic_filter_csv_rows(writer, filters or {})
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
    _write_distribution('Department distribution', demo['department'], 'department')
    _write_distribution('Year level distribution', demo['year_level'], 'year_level')
    _write_distribution('Course distribution', demo['course'], 'course')
    _write_distribution('Blood type distribution', data['blood_types'], 'blood_type')
    _write_distribution(
        'Medical records by department (period)',
        [
            {
                'department': item['patient__patient_profile__department'] or 'Unknown',
                'count': item['count'],
            }
            for item in data['health_by_department']
        ],
        'department',
    )
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
        'Appointments by department (period)',
        [
            {
                'department': item['patient__patient_profile__department'] or 'Unknown',
                'count': item['count'],
            }
            for item in data['appt_by_department']
        ],
        'department',
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
    _write_distribution(
        'Appointments by year level (period)',
        [
            {
                'year_level': item['patient__patient_profile__year_level'] or 'Unknown',
                'count': item['count'],
            }
            for item in data['appt_by_year']
        ],
        'year_level',
    )


def write_population_period_csv(writer, date_from, date_to, filters=None):
    data = population_health_data(date_from, date_to, filters=filters)
    writer.writerow(['Population period activity'])
    writer.writerow(['Period from', date_from])
    writer.writerow(['Period to', date_to])
    write_academic_filter_csv_rows(writer, filters or {})
    writer.writerow(['Medical records by department'])
    writer.writerow(['Department', 'Count'])
    for item in data['health_by_department']:
        writer.writerow([
            item['patient__patient_profile__department'] or 'Unknown',
            item['count'],
        ])
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
    writer.writerow([])
    writer.writerow(['Appointments by year level'])
    writer.writerow(['Year level', 'Count'])
    for item in data['appt_by_year']:
        writer.writerow([
            item['patient__patient_profile__year_level'] or 'Unknown',
            item['count'],
        ])


def write_academic_summary_csv(writer, date_from, date_to, filters=None):
    data = academic_correlation_data(date_from, date_to, filters=filters)
    writer.writerow(['Academic Correlation'])
    writer.writerow(['Period from', date_from])
    writer.writerow(['Period to', date_to])
    write_academic_filter_csv_rows(writer, filters or {})
    writer.writerow(['Summary KPIs'])
    writer.writerow(['Metric', 'Value'])
    writer.writerow(['Total visits', data['total_visits']])
    writer.writerow(['Patients with 5+ visits', data['high_visit_patients']])
    writer.writerow(['Emergency visits', data['emergency_total']])
    writer.writerow([])
    writer.writerow(['Visits by department (top 5)'])
    writer.writerow(['Department', 'Visits'])
    for row in data['visits_by_department']:
        writer.writerow([
            row['patient__patient_profile__department'] or 'Unknown',
            row['count'],
        ])
    writer.writerow([])
    writer.writerow(['Visits by course'])
    writer.writerow(['Course', 'Visits'])
    for row in data['visits_by_course']:
        writer.writerow([
            row['patient__patient_profile__course'] or 'Unknown',
            row['count'],
        ])
    writer.writerow([])
    writer.writerow(['Frequent clinic visitors'])
    writer.writerow(['Patient', 'Email', 'Department', 'Course', 'Year level', 'Visits'])
    for row in data['frequent_visitors']:
        name = f"{row['patient__first_name']} {row['patient__last_name']}".strip()
        writer.writerow([
            name,
            row['patient__email'],
            row['patient__patient_profile__department'] or '',
            row['patient__patient_profile__course'] or '',
            row['patient__patient_profile__year_level'] or '',
            row['visit_count'],
        ])
    writer.writerow([])
    writer.writerow(['Emergency visits by department'])
    writer.writerow(['Department', 'Count'])
    for row in data['emergency_by_department']:
        writer.writerow([
            row['patient__patient_profile__department'] or 'Unknown',
            row['count'],
        ])
    writer.writerow([])
    writer.writerow(['Emergency visits by year level'])
    writer.writerow(['Year level', 'Count'])
    for row in data['emergency_by_year']:
        writer.writerow([
            row['patient__patient_profile__year_level'] or 'Unknown',
            row['count'],
        ])
    writer.writerow([])
    writer.writerow(['Emergency visits by course'])
    writer.writerow(['Course', 'Count'])
    for row in data['emergency_visits']:
        writer.writerow([
            row['patient__patient_profile__course'] or 'Unknown',
            row['count'],
        ])


def write_academic_visitors_csv(writer, date_from, date_to, filters=None):
    data = academic_correlation_data(date_from, date_to, filters=filters)
    writer.writerow(['Frequent clinic visitors'])
    writer.writerow(['Period from', date_from])
    writer.writerow(['Period to', date_to])
    write_academic_filter_csv_rows(writer, filters or {})
    writer.writerow(['Patient', 'Email', 'Department', 'Course', 'Year level', 'Visits'])
    for row in data['frequent_visitors']:
        name = f"{row['patient__first_name']} {row['patient__last_name']}".strip()
        writer.writerow([
            name,
            row['patient__email'],
            row['patient__patient_profile__department'] or '',
            row['patient__patient_profile__course'] or '',
            row['patient__patient_profile__year_level'] or '',
            row['visit_count'],
        ])


def write_staff_dashboard_csv(writer, user, date_from, date_to, filters=None):
    from appointments.models import Appointment

    filters = filters or {}
    my_appointments = apply_academic_filters(
        Appointment.objects.filter(doctor=user, date__gte=date_from, date__lte=date_to),
        filters,
    )
    trend = list(
        my_appointments.values(day=F('date'))
        .annotate(count=Count('id')).order_by('day')
    )
    diagnoses = illness_stats(date_from, date_to, doctor=user, filters=filters)[:10]
    hourly_series, _hourly_peak, _hourly_has_data = hourly_chart_series(
        appointment_by_hour(date_from, date_to, doctor=user, filters=filters),
    )

    writer.writerow(['Staff Analytics Dashboard'])
    writer.writerow(['Exported by', user.get_full_name() or user.email])
    writer.writerow(['Period from', date_from])
    writer.writerow(['Period to', date_to])
    write_academic_filter_csv_rows(writer, filters)
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


def write_health_trends_csv(writer, request, date_from, date_to):
    trends = filtered_health_trend_records(request)
    illness_q = (request.GET.get('illness_category') or '').strip()
    filters = filters_from_request(request)
    live_stats = illness_stats(
        date_from, date_to,
        diagnosis_query=illness_q or None,
        filters=filters,
    )

    writer.writerow(['Health Trends'])
    writer.writerow(['Period from', date_from])
    writer.writerow(['Period to', date_to])
    if illness_q:
        writer.writerow(['Illness filter', illness_q])
    write_academic_filter_csv_rows(writer, filters)
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


def write_admin_dashboard_csv(writer, date_from, date_to, filters=None):
    from appointments.models import Appointment
    from medical_records.models import MedicalRecord
    from feedback.models import Feedback

    filters = filters or {}
    total_patients = User.objects.filter(role__in=PATIENT_ROLE_VALUES).count()
    total_staff = User.objects.filter(role__in=['staff', 'doctor']).count()
    total_appointments = apply_academic_filters(
        Appointment.objects.filter(date__gte=date_from, date__lte=date_to),
        filters,
    ).count()
    total_records = apply_academic_filters(
        MedicalRecord.objects.filter(
            created_at__date__gte=date_from, created_at__date__lte=date_to,
        ),
        filters,
    ).count()
    avg_feedback = Feedback.objects.aggregate(avg=Avg('rating'))['avg'] or 0
    volume = appointment_volume(date_from, date_to, filters=filters)
    by_type = appointment_by_type(date_from, date_to, filters=filters)
    diagnoses = illness_stats(date_from, date_to, filters=filters)[:15]
    demo = student_demographics(filters=filters)

    writer.writerow(['Clinic Analytics Dashboard'])
    writer.writerow(['Period from', date_from])
    writer.writerow(['Period to', date_to])
    write_academic_filter_csv_rows(writer, filters)
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
    writer.writerow([])
    writer.writerow(['Patients by department'])
    writer.writerow(['Department', 'Count'])
    for row in demo['department']:
        writer.writerow([row['department'] or 'Unknown', row['count']])


def write_financial_summary_csv(writer, date_from, date_to):
    summary = financial_summary(date_from, date_to)
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
            financial_category_label(row['category']),
            row['total'],
        ])
    writer.writerow([])
    writer.writerow(['Monthly overview'])
    writer.writerow(['Month', 'Expenses (PHP)', 'Income (PHP)'])
    for month, totals in financial_monthly_table(summary['monthly']):
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
