"""Appointment detail view."""

import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme

from appointments.models import Appointment
from core.access_control import AccessReason, access_denied_response
from core.clinical_permissions import can_write_appointments
from core.decorators import role_required
from core.htmx_utils import is_htmx_request, htmx_add_toast
from core.notification_delivery import notify_user
from core.roles import ROLE_DOCTOR, ROLE_PATIENT, role_matches
from core.settings_service import get_clinic_settings

from .list import _appointment_list_htmx_oob_response, _is_appointment_list_htmx_context

logger = logging.getLogger(__name__)


@login_required
@role_required('student', 'staff', 'doctor', 'admin')
def appointment_detail(request, appointment_id):
    appointment = get_object_or_404(
        Appointment.objects.select_related('patient', 'patient__patient_profile', 'doctor', 'doctor__staff_profile').prefetch_related('dental_records', 'medicalrecord_set'),
        id=appointment_id,
    )
    
    # Check permissions (admin can view all)
    if role_matches(request.user.role, ROLE_PATIENT) and appointment.patient != request.user:
        messages.error(request, 'Access denied')
        return redirect('appointments:appointment_list')
    elif request.user.role == ROLE_DOCTOR and appointment.doctor != request.user:
        messages.error(request, 'Access denied')
        return redirect('appointments:appointment_list')
    
    if request.method == 'POST':
        next_url = request.POST.get('next')
        is_htmx = is_htmx_request(request)
        list_htmx = is_htmx and (
            request.POST.get('htmx_from_appt_list') == '1' or _is_appointment_list_htmx_context(request)
        )

        def htmx_error(message, status_code=400):
            if list_htmx:
                response = HttpResponse('', status=status_code)
                return htmx_add_toast(response, message, 'error')
            if is_htmx:
                response = HttpResponse('', status=status_code)
                return htmx_add_toast(response, message, 'error')
            messages.error(request, message)
            return None

        success_message = None
        email_feedback = None
        email_feedback_type = 'success'

        if can_write_appointments(request.user, appointment):
            status = request.POST.get('status')
            notes = request.POST.get('notes')
            previous_status = appointment.status

            if previous_status == 'cancelled':
                if status and status != 'cancelled':
                    err = htmx_error('Cancelled appointments cannot be changed.')
                    if err:
                        return err
                if notes is not None:
                    appointment.notes = notes
                    appointment.save(update_fields=['notes', 'updated_at'])
                    success_message = 'Notes updated.'
            else:
                if status:
                    appointment.status = status
                if notes is not None:
                    appointment.notes = notes
                appointment.save()

                if status and appointment.status != previous_status:
                    from core.guest_auth import resolve_patient_contact_email
                    from core.notification_delivery import format_email_send_error

                    status_to_transaction = {
                        'pending': 'appointment_reminder',
                        'confirmed': 'appointment_confirmed',
                        'completed': 'appointment_completed',
                        'missed': 'appointment_reminder',
                        'cancelled': 'appointment_cancelled',
                    }
                    contact = resolve_patient_contact_email(appointment.patient)
                    emailed = False
                    email_error = ''

                    if appointment.status == 'completed':
                        notify_user(
                            appointment.patient,
                            title='Appointment Completed',
                            message=(
                                f'Your appointment on {appointment.date.strftime("%B %d, %Y")} '
                                f'is complete. Your results are ready to view.'
                            ),
                            notification_type='appointment',
                            transaction_type='appointment_completed',
                            related_id=appointment.id,
                            send_email=False,
                        )
                        from core.guest_emails import email_appointment_results_ready

                        try:
                            emailed = email_appointment_results_ready(
                                request, appointment, created_by=request.user
                            )
                        except Exception as email_exc:
                            email_error = format_email_send_error(email_exc)
                            emailed = False
                        if not contact:
                            email_feedback = 'Patient has no contact email — results email was not sent.'
                            email_feedback_type = 'warning'
                        elif emailed:
                            email_feedback = f'Results email sent to {contact}.'
                        else:
                            detail = email_error or 'check clinic email settings / EMAIL_BACKEND'
                            email_feedback = f'Results email was not sent ({detail}).'
                            email_feedback_type = 'warning'
                    else:
                        notify_user(
                            appointment.patient,
                            title='Appointment Update',
                            message=(
                                f'Your appointment status has been updated to '
                                f'{appointment.get_status_display()}'
                            ),
                            notification_type='appointment',
                            transaction_type=status_to_transaction.get(
                                appointment.status, 'appointment_reminder'
                            ),
                            related_id=appointment.id,
                            send_email=False,
                        )
                        from core.guest_emails import email_appointment_updated

                        try:
                            emailed = email_appointment_updated(
                                request,
                                appointment,
                                previous_status=previous_status,
                                created_by=request.user,
                            )
                        except Exception as email_exc:
                            email_error = format_email_send_error(email_exc)
                            emailed = False
                        if not contact:
                            email_feedback = 'Patient has no contact email — update email was not sent.'
                            email_feedback_type = 'warning'
                        elif emailed:
                            email_feedback = f'Update email sent to {contact}.'
                        else:
                            detail = email_error or 'check clinic email settings / EMAIL_BACKEND'
                            email_feedback = f'Update email was not sent ({detail}).'
                            email_feedback_type = 'warning'

                        if (
                            appointment.status == 'cancelled'
                            and request.user.id != appointment.doctor_id
                        ):
                            from core.guest_emails import email_doctor_appointment_cancelled

                            try:
                                email_doctor_appointment_cancelled(
                                    request,
                                    appointment,
                                    cancelled_by=request.user,
                                )
                            except Exception:
                                logger.warning(
                                    'Doctor appointment cancelled email failed',
                                    exc_info=True,
                                )

                success_message = f'Appointment updated to {appointment.get_status_display()}.'

        elif role_matches(request.user.role, ROLE_PATIENT) and appointment.patient == request.user:
            status = request.POST.get('status')
            if status == 'cancelled' and appointment.status in ('pending', 'confirmed'):
                from datetime import datetime as dt

                cutoff_hours = get_clinic_settings().cancellation_cutoff_hours
                appt_start = timezone.make_aware(
                    dt.combine(appointment.date, appointment.time),
                    timezone.get_current_timezone(),
                )
                from datetime import timedelta

                if timezone.now() + timedelta(hours=cutoff_hours) > appt_start:
                    err = htmx_error(
                        f'Cancellations must be at least {cutoff_hours} hours before the appointment.',
                    )
                    if err:
                        return err

                appointment.status = 'cancelled'
                appointment.save()

                notify_user(
                    appointment.doctor,
                    title='Appointment Cancelled',
                    message=f'Appointment with {request.user.get_full_name()} has been cancelled',
                    notification_type='appointment',
                    transaction_type='appointment_cancelled',
                    related_id=appointment.id,
                    send_email=False,
                )

                try:
                    from core.guest_emails import email_doctor_appointment_cancelled

                    email_doctor_appointment_cancelled(
                        request,
                        appointment,
                        cancelled_by=request.user,
                    )
                except Exception:
                    logger.warning(
                        'Doctor appointment cancelled email failed',
                        exc_info=True,
                    )

                success_message = 'Appointment cancelled successfully!'
            else:
                err = htmx_error('Cannot cancel this appointment')
                if err:
                    return err
        else:
            err = htmx_error('Access denied', status_code=403)
            if err:
                return err
            return access_denied_response(request, status_code=403, reason=AccessReason.FORBIDDEN)

        if list_htmx and success_message:
            combined = success_message
            if email_feedback:
                combined = f'{combined} {email_feedback}'
            return _appointment_list_htmx_oob_response(
                request,
                combined,
                email_feedback_type if email_feedback else 'success',
            )

        if success_message:
            messages.success(request, success_message)
        if email_feedback:
            if email_feedback_type == 'warning':
                messages.warning(request, email_feedback)
            else:
                messages.success(request, email_feedback)

        if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
            return redirect(next_url)

        return redirect('appointments:appointment_detail', appointment_id=appointment.id)
    
    return render(request, 'appointments/appointment_detail.html', {
        'appointment': appointment,
    })
