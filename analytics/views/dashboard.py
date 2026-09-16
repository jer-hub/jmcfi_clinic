"""Main analytics dashboard (role-based)."""

from collections import defaultdict

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, F
from django.shortcuts import redirect, render
from django.urls import reverse
from urllib.parse import urlencode
from django.utils import timezone

from core.roles import PATIENT_ROLE_VALUES, is_patient_role
from core.utils import parse_date

from analytics.academic_filters import (
    analytics_filter_context,
    apply_academic_filters,
)
from analytics.forms import DateRangeFilterForm
from analytics.services import (
    appointment_by_hour,
    appointment_by_type,
    appointment_by_weekday,
    appointment_volume,
    diagnosis_aggregate_key,
    diagnosis_display_name,
    financial_summary,
    hourly_chart_series,
    concern_kpis,
    illness_stats,
    patient_chart_kpis,
    student_demographics,
    student_visit_history,
)
from analytics.views.helpers import (
    _filters_from_request,
    _get_date_range,
    _period_presets_for_request,
)

User = get_user_model()


def _concerns_analysis_href(date_from, date_to, academic_query=''):
    base = reverse('analytics:concerns_analysis')
    qs = urlencode({
        'date_from': date_from.isoformat(),
        'date_to': date_to.isoformat(),
    })
    suffix = (academic_query or '').lstrip('&')
    if suffix:
        return f'{base}?{qs}&{suffix}'
    return f'{base}?{qs}'


def _patient_charts_analysis_href(date_from, date_to, academic_query=''):
    base = reverse('analytics:patient_charts_analysis')
    qs = urlencode({
        'date_from': date_from.isoformat(),
        'date_to': date_to.isoformat(),
    })
    suffix = (academic_query or '').lstrip('&')
    if suffix:
        return f'{base}?{qs}&{suffix}'
    return f'{base}?{qs}'


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
    filters = _filters_from_request(request)
    user = request.user

    context = {
        'date_from': date_from,
        'date_to': date_to,
        'filter_form': DateRangeFilterForm(initial={'date_from': date_from, 'date_to': date_to}),
    }
    context.update(analytics_filter_context(request, date_from, date_to))
    context['period_presets'] = _period_presets_for_request(request, date_from, date_to)
    context['export_variant'] = 'admin' if user.role == 'admin' else 'staff'

    if is_patient_role(user.role):
        from medical_records.models import MedicalRecord
        from appointments.models import Appointment

        records = MedicalRecord.objects.filter(patient=user).order_by('-created_at')
        appointments = Appointment.objects.filter(patient=user)
        total_appointments = appointments.count()
        completed_appointments = appointments.filter(status='completed').count()
        appointment_history = student_visit_history(user, months=6)

        recent_diag_raw = list(
            records.exclude(diagnosis='').values('diagnosis')
            .annotate(count=Count('id')).order_by('-count')[:25]
        )
        recent_diag_map = defaultdict(int)
        display_names = {}
        for item in recent_diag_raw:
            key = diagnosis_aggregate_key(item['diagnosis'])
            recent_diag_map[key] += item['count']
            if key not in display_names:
                display_names[key] = diagnosis_display_name(key, item['diagnosis'])

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

        my_appointments = apply_academic_filters(
            Appointment.objects.filter(doctor=user, date__gte=date_from, date__lte=date_to),
            filters,
        )
        hourly_series, hourly_peak, hourly_has_data = hourly_chart_series(
            appointment_by_hour(date_from, date_to, doctor=user, filters=filters),
        )
        top_diagnoses = illness_stats(date_from, date_to, doctor=user, filters=filters)[:10]
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
        })
        if user.role == 'staff':
            from pharmacy.services.reports import build_pharmacy_analytics_summary

            context['pharmacy_analytics'] = build_pharmacy_analytics_summary(date_from, date_to)
        concern_stats = concern_kpis(date_from, date_to, filters=filters)
        chart_stats = patient_chart_kpis(date_from, date_to, filters=filters)
        context.update({
            'total_concerns': concern_stats['total_records'],
            'concerns_analysis_href': _concerns_analysis_href(
                date_from, date_to, context.get('academic_query', ''),
            ),
            'total_patient_charts': chart_stats['total_charts'],
            'patient_charts_analysis_href': _patient_charts_analysis_href(
                date_from, date_to, context.get('academic_query', ''),
            ),
        })
        return render(request, 'analytics/dashboard_staff.html', context)

    else:
        from appointments.models import Appointment
        from medical_records.models import MedicalRecord
        from feedback.models import Feedback

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

        concern_stats = concern_kpis(date_from, date_to, filters=filters)
        chart_stats = patient_chart_kpis(date_from, date_to, filters=filters)
        context.update({
            'total_patients': total_patients,
            'total_staff': total_staff,
            'total_appointments': total_appointments,
            'total_records': total_records,
            'total_concerns': concern_stats['total_records'],
            'concerns_analysis_href': _concerns_analysis_href(
                date_from, date_to, context.get('academic_query', ''),
            ),
            'total_patient_charts': chart_stats['total_charts'],
            'patient_charts_analysis_href': _patient_charts_analysis_href(
                date_from, date_to, context.get('academic_query', ''),
            ),
            'avg_feedback': round(avg_feedback, 1),
            'illness_stats': illness_stats(date_from, date_to, filters=filters)[:15],
            'appointment_volume': appointment_volume(date_from, date_to, filters=filters),
            'appointment_by_type': appointment_by_type(date_from, date_to, filters=filters),
            'appointment_by_hour': appointment_by_hour(date_from, date_to, filters=filters),
            'appointment_by_weekday': appointment_by_weekday(date_from, date_to, filters=filters),
            'demographics': student_demographics(filters=filters),
            'financial_summary': financial_summary(date_from, date_to),
            'pharmacy_analytics': build_pharmacy_analytics_summary(date_from, date_to),
        })
        context.update(build_admin_calendar_context(
            year=cal_year,
            month=cal_month,
            selected_date=cal_selected,
            user=user,
        ))
        context['period_presets'] = _period_presets_for_request(request, date_from, date_to)
        return render(request, 'analytics/dashboard_admin.html', context)
