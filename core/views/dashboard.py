"""Dashboard views."""

from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone

from appointments.calendar_service import build_dashboard_calendar_context
from appointments.models import Appointment
from core.roles import ROLE_PATIENT, role_matches
from core.utils import user_visible_notifications
from dental_records.models import DentalRecord
from document_request.models import DocumentRequest
from medical_records.models import MedicalRecord


def _appointment_list_url_for_local_date(d):
    """Appointment list filtered to a single local calendar day."""
    query = urlencode({'date_from': d.isoformat(), 'date_to': d.isoformat()})
    return f"{reverse('appointments:appointment_list')}?{query}"


def _appointment_list_url_status(status: str) -> str:
    """Appointment list filtered by appointment status (GET param matches list view)."""
    query = urlencode({'status': status})
    return f"{reverse('appointments:appointment_list')}?{query}"


@login_required
def dashboard(request):
    """Main dashboard view - role-based content"""
    if request.user.role == 'admin':
        from analytics.views import render_analytics_dashboard
        return render_analytics_dashboard(request)

    context = {}
    
    if role_matches(request.user.role, ROLE_PATIENT):
        from health_forms_services.models import HealthProfileForm

        pending_health_forms_qs = HealthProfileForm.objects.filter(
            user=request.user,
            status=HealthProfileForm.Status.INCOMPLETE,
        ).order_by('-updated_at')
        pending_health_forms = list(pending_health_forms_qs[:5])
        pending_health_forms_count = pending_health_forms_qs.count()
        if pending_health_forms_count == 1:
            pending_health_forms_url = reverse(
                'health_forms_services:edit_form',
                kwargs={'pk': pending_health_forms[0].pk},
            )
        else:
            pending_health_forms_url = (
                reverse('health_forms_services:forms_list') + '?status=incomplete'
            )

        context.update({
            'recent_records': MedicalRecord.objects.filter(
                patient=request.user
            ).order_by('-created_at')[:3],
            'unread_notifications': user_visible_notifications(request.user).filter(
                is_read=False,
            ).count(),
            'pending_certificates': DocumentRequest.objects.filter(
                patient=request.user,
                status=DocumentRequest.Status.PENDING_REVIEW,
            ).count(),
            'pending_health_forms': pending_health_forms,
            'pending_health_forms_count': pending_health_forms_count,
            'pending_health_forms_url': pending_health_forms_url,
            'total_appointments': Appointment.objects.filter(patient=request.user).count(),
            'total_records': MedicalRecord.objects.filter(patient=request.user).count(),
            'total_dental_records': DentalRecord.objects.filter(patient=request.user).count(),
            'approved_certificates': DocumentRequest.objects.filter(
                patient=request.user,
                status=DocumentRequest.Status.COMPLETED,
            ).count(),
        })
    
    elif request.user.role == 'doctor':
        today = timezone.now().date()
        context.update({
            'today_appointments': Appointment.objects.filter(
                doctor=request.user,
                date=today
            ).order_by('time'),
            'pending_appointments': Appointment.objects.filter(
                doctor=request.user,
                status='pending'
            ).count(),
            'pending_certificates': DocumentRequest.objects.filter(
                status=DocumentRequest.Status.PENDING_REVIEW,
            ).count(),
            'total_patients': MedicalRecord.objects.filter(
                doctor=request.user
            ).values('patient').distinct().count(),
            'completed_appointments': Appointment.objects.filter(
                doctor=request.user,
                status='completed'
            ).count(),
            'recent_records': MedicalRecord.objects.filter(
                doctor=request.user
            ).order_by('-created_at')[:5],
            'appointment_list_today_url': _appointment_list_url_for_local_date(today),
            'appointment_list_pending_url': _appointment_list_url_status('pending'),
        })

    elif request.user.role == 'staff':
        today = timezone.now().date()
        context.update({
            'today_appointments': Appointment.objects.filter(
                date=today
            ).order_by('time'),
            'pending_appointments': Appointment.objects.filter(
                status='pending'
            ).count(),
            'total_patients': MedicalRecord.objects.values('patient').distinct().count(),
            'completed_appointments': Appointment.objects.filter(
                status='completed'
            ).count(),
            'recent_records': MedicalRecord.objects.order_by('-created_at')[:5],
            'appointment_list_today_url': _appointment_list_url_for_local_date(today),
            'appointment_list_pending_url': _appointment_list_url_status('pending'),
        })

    if role_matches(request.user.role, ROLE_PATIENT, 'doctor', 'staff'):
        context.update(build_dashboard_calendar_context(request.user))

    return render(request, 'core/dashboard.html', context)
