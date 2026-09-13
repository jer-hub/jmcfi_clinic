"""Compliance & accreditation reporting views."""

import json

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from core.decorators import admin_required
from core.roles import PATIENT_ROLE_VALUES
from core.utils import paginate_queryset

from analytics.academic_filters import (
    active_filter_labels,
    analytics_filter_context,
    apply_academic_filters,
    page_window_numbers,
)
from analytics.forms import ComplianceReportForm
from analytics.models import ComplianceReport
from analytics.services import filtered_compliance_reports, illness_stats
from analytics.views.helpers import (
    _get_date_range,
    _period_presets_for_request,
)

User = get_user_model()


@login_required
@admin_required
def compliance_reports(request):
    """List and manage compliance reports."""
    date_from, date_to = _get_date_range(request)
    reports_qs, report_filter, _filters = filtered_compliance_reports(request)
    type_labels = dict(ComplianceReport.REPORT_TYPES)
    reports_page = paginate_queryset(reports_qs, request, per_page=10)
    context = {
        'reports': reports_page,
        'page_window': page_window_numbers(reports_page),
        'report_types': ComplianceReport.REPORT_TYPES,
        'selected_type': report_filter,
        'filter_label': type_labels.get(report_filter, 'All types'),
        'reports_total': reports_qs.count(),
        'reports_draft': reports_qs.filter(status='draft').count(),
        'reports_final': reports_qs.filter(status='final').count(),
        'reports_submitted': reports_qs.filter(status='submitted').count(),
        'date_from': date_from,
        'date_to': date_to,
        'export_variant': 'compliance',
    }
    context.update(analytics_filter_context(request, date_from, date_to))
    context['period_presets'] = _period_presets_for_request(request, date_from, date_to)
    if report_filter:
        from urllib.parse import quote
        context['extra_query'] = f'&type={quote(report_filter)}'
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

            date_from = report.period_start
            date_to = report.period_end
            from appointments.models import Appointment
            from medical_records.models import MedicalRecord

            filters = {
                'department': form.cleaned_data.get('department') or '',
                'course': form.cleaned_data.get('course') or '',
                'year_level': form.cleaned_data.get('year_level') or '',
            }
            if not filters['department']:
                filters['course'] = ''
                filters['year_level'] = ''
            appt_qs = apply_academic_filters(
                Appointment.objects.filter(date__gte=date_from, date__lte=date_to),
                filters,
            )
            mr_qs = apply_academic_filters(
                MedicalRecord.objects.filter(
                    created_at__date__gte=date_from, created_at__date__lte=date_to,
                ),
                filters,
            )

            data = {
                'academic_filters': filters,
                'total_appointments': appt_qs.count(),
                'completed_appointments': appt_qs.filter(status='completed').count(),
                'total_records': mr_qs.count(),
                'total_patients': User.objects.filter(role__in=PATIENT_ROLE_VALUES).count(),
                'total_staff': User.objects.filter(role__in=['staff', 'doctor']).count(),
                'top_diagnoses': illness_stats(date_from, date_to, filters=filters)[:10],
                'generated_at': timezone.now().isoformat(),
            }
            report.data_json = data
            report.save()
            messages.success(request, f'Compliance report "{report.title}" generated.')
            return redirect('analytics:compliance_reports')
    else:
        form = ComplianceReportForm()

    from core.academic_catalog import patient_catalog_context

    catalog = patient_catalog_context()
    dept = (form['department'].value() or '').strip()
    course = (form['course'].value() or '').strip() if dept else ''
    year = (form['year_level'].value() or '').strip() if dept else ''
    return render(request, 'analytics/compliance_report_form.html', {
        'form': form,
        'college_options': catalog['college_options'],
        'course_options_by_college_json': catalog['course_options_by_college_json'],
        'year_level_options_by_college_json': catalog['year_level_options_by_college_json'],
        'cascade_config_json': json.dumps({
            'department': dept,
            'course': course,
            'year_level': year,
        }),
    })


@login_required
@admin_required
def compliance_report_detail(request, pk):
    """View compliance report details."""
    report = get_object_or_404(ComplianceReport, pk=pk)
    stored_filters = (report.data_json or {}).get('academic_filters') or {}
    return render(request, 'analytics/compliance_report_detail.html', {
        'report': report,
        'stored_academic_labels': active_filter_labels(stored_filters),
    })
