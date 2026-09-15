"""Analytics CSV export view."""

import csv

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseForbidden

from core.decorators import role_required

from analytics.academic_filters import apply_academic_filters, write_academic_filter_csv_rows
from analytics.models import ExportLog, FinancialRecord
from analytics.services import (
    academic_correlation_data,
    filtered_health_trend_records,
    illness_stats,
    resource_utilization_staff_stats,
    utilization_records_qs,
    write_academic_summary_csv,
    write_academic_visitors_csv,
    write_admin_dashboard_csv,
    write_compliance_index_csv,
    write_concerns_csv,
    write_concerns_summary_csv,
    write_financial_summary_csv,
    write_health_trends_csv,
    write_population_period_csv,
    write_population_summary_csv,
    write_predictive_csv,
    write_resource_utilization_csv,
    write_staff_dashboard_csv,
)
from analytics.views.helpers import _filters_from_request, _get_date_range


@login_required
@role_required('staff', 'doctor', 'admin')
def export_report(request):
    """Export analytics data as CSV or Excel-compatible CSV."""
    report_type = request.GET.get('report', 'appointments')
    date_from, date_to = _get_date_range(request)
    filters = _filters_from_request(request)
    illness_q = (request.GET.get('illness_category') or '').strip()
    concern_q = (request.GET.get('q') or '').strip()

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = (
        f'attachment; filename="analytics_{report_type}_{date_from}_to_{date_to}.csv"'
    )
    writer = csv.writer(response)

    if report_type == 'staff_dashboard':
        if request.user.role not in ('staff', 'doctor'):
            return HttpResponseForbidden()
        write_staff_dashboard_csv(writer, request.user, date_from, date_to, filters=filters)

    elif report_type == 'admin_dashboard':
        if request.user.role != 'admin':
            return HttpResponseForbidden()
        write_admin_dashboard_csv(writer, date_from, date_to, filters=filters)

    elif report_type == 'my_appointments':
        if request.user.role not in ('staff', 'doctor'):
            return HttpResponseForbidden()
        from appointments.models import Appointment
        write_academic_filter_csv_rows(writer, filters)
        writer.writerow(['Date', 'Time', 'Patient', 'Type', 'Status', 'Notes'])
        qs = apply_academic_filters(
            Appointment.objects.filter(
                doctor=request.user,
                date__gte=date_from,
                date__lte=date_to,
            ),
            filters,
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
        write_academic_filter_csv_rows(writer, filters)
        writer.writerow(['Date', 'Time', 'Patient', 'Doctor', 'Type', 'Status'])
        qs = apply_academic_filters(
            Appointment.objects.filter(date__gte=date_from, date__lte=date_to),
            filters,
        ).select_related('patient', 'doctor').order_by('date', 'time')
        for a in qs:
            writer.writerow([
                a.date, a.time,
                a.patient.get_full_name() if a.patient else '',
                a.doctor.get_full_name() if a.doctor else '',
                a.get_appointment_type_display(),
                a.get_status_display(),
            ])

    elif report_type == 'medical_records':
        from medical_records.models import MedicalRecord
        write_academic_filter_csv_rows(writer, filters)
        writer.writerow(['Date', 'Patient', 'Doctor', 'Diagnosis', 'Treatment'])
        qs = apply_academic_filters(
            MedicalRecord.objects.filter(
                created_at__date__gte=date_from, created_at__date__lte=date_to,
            ),
            filters,
        ).select_related('patient', 'doctor').order_by('-created_at')
        for r in qs:
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
            write_financial_summary_csv(writer, date_from, date_to)
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

    elif report_type == 'concerns':
        write_concerns_csv(writer, date_from, date_to, filters=filters, search=concern_q or None)

    elif report_type == 'concerns_summary':
        write_concerns_summary_csv(
            writer, date_from, date_to, filters=filters, search=concern_q or None,
        )

    elif report_type == 'health_trends':
        writer.writerow(['Academic Year', 'Semester', 'Illness', 'Cases', 'Notes'])
        for t in filtered_health_trend_records(request).order_by(
            '-academic_year', 'semester', 'illness_category',
        ):
            writer.writerow([
                t.academic_year, t.get_semester_display(),
                t.illness_category, t.case_count, t.notes,
            ])

    elif report_type == 'health_trends_live':
        write_academic_filter_csv_rows(writer, filters)
        if illness_q:
            writer.writerow(['Illness filter', illness_q])
            writer.writerow([])
        writer.writerow(['Diagnosis', 'Count'])
        for row in illness_stats(
            date_from, date_to,
            diagnosis_query=illness_q or None,
            filters=filters,
        ):
            writer.writerow([row['diagnosis'], row['count']])

    elif report_type == 'health_trends_summary':
        write_health_trends_csv(writer, request, date_from, date_to)

    elif report_type == 'resource_utilization_summary':
        write_resource_utilization_csv(writer, date_from, date_to, filters=filters)

    elif report_type == 'resource_utilization_daily':
        writer.writerow([
            'Date', 'Consultations', 'Avg minutes', 'Throughput',
            'Staff on duty', 'Peak hour', 'Efficiency score', 'Notes',
        ])
        for r in utilization_records_qs(date_from, date_to).order_by('-date'):
            writer.writerow([
                r.date, r.total_consultations, r.avg_consultation_minutes,
                r.patient_throughput, r.staff_on_duty, r.peak_hour or '',
                r.efficiency_score, r.notes,
            ])

    elif report_type == 'resource_utilization_staff':
        write_academic_filter_csv_rows(writer, filters)
        writer.writerow(['Staff member', 'Completed appointments'])
        for row in resource_utilization_staff_stats(date_from, date_to, filters=filters):
            name = f"{row['doctor__first_name']} {row['doctor__last_name']}".strip()
            writer.writerow([name, row['total']])

    elif report_type == 'population_summary':
        write_population_summary_csv(writer, date_from, date_to, filters=filters)

    elif report_type == 'population_period':
        write_population_period_csv(writer, date_from, date_to, filters=filters)

    elif report_type == 'academic_summary':
        write_academic_summary_csv(writer, date_from, date_to, filters=filters)

    elif report_type == 'academic_visitors':
        write_academic_visitors_csv(writer, date_from, date_to, filters=filters)

    elif report_type == 'academic_emergency':
        data = academic_correlation_data(date_from, date_to, filters=filters)
        writer.writerow(['Emergency visits by course'])
        writer.writerow(['Period from', date_from])
        writer.writerow(['Period to', date_to])
        write_academic_filter_csv_rows(writer, filters)
        writer.writerow(['Course', 'Count'])
        for row in data['emergency_visits']:
            writer.writerow([
                row['patient__patient_profile__course'] or 'Unknown',
                row['count'],
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

    elif report_type in ('predictive_insights', 'predictive_hourly'):
        write_predictive_csv(
            writer, request, date_from, date_to, filters,
            report_type=report_type,
        )

    elif report_type == 'compliance_index':
        if request.user.role != 'admin':
            return HttpResponseForbidden()
        write_compliance_index_csv(writer, request, date_from, date_to, filters)

    elif report_type == 'demographics':
        from core.models import PatientProfile
        write_academic_filter_csv_rows(writer, filters)
        writer.writerow(['Patient ID', 'Department', 'Course', 'Year Level', 'Gender', 'Blood Type'])
        profile_qs = PatientProfile.objects.select_related('user').order_by('patient_id')
        if filters.get('department'):
            profile_qs = profile_qs.filter(department=filters['department'])
        if filters.get('course'):
            profile_qs = profile_qs.filter(course=filters['course'])
        if filters.get('year_level'):
            profile_qs = profile_qs.filter(year_level=filters['year_level'])
        for p in profile_qs:
            writer.writerow([
                p.patient_id, p.department, p.course, p.year_level, p.gender, p.blood_type,
            ])

    ExportLog.objects.create(
        report_name=report_type,
        export_format='csv',
        exported_by=request.user,
    )

    return response
