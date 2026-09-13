"""Dental record status transition views."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse

from appointments.models import Appointment
from core.decorators import role_required
from core.guest_auth import is_guest_user
from core.htmx_utils import htmx_add_toast, htmx_add_trigger
from dental_records.models import DentalRecord
from .helpers import _audit_dental, _dental_action_bar_context
from .list import (
    _build_dental_list_page_context,
    _effective_dental_list_get_params,
)


@login_required
@role_required('doctor')
def complete_appointment(request, record_id):
    """Mark the associated appointment as completed"""
    dental_record = get_object_or_404(DentalRecord, pk=record_id)
    
    if not dental_record.appointment:
        messages.error(request, 'No appointment associated with this dental record.')
        return redirect('dental_records:dental_record_edit', record_id=record_id)
    
    if dental_record.appointment.status != 'completed':
        dental_record.appointment.status = 'completed'
        dental_record.appointment.save()
        _audit_dental(request, dental_record, 'edit', section='status')
        messages.success(request, 'Appointment marked as completed successfully.')
    else:
        messages.info(request, 'Appointment is already completed.')
    
    return redirect('dental_records:dental_record_edit', record_id=record_id)


@login_required
@role_required('doctor', 'admin')
def dental_record_status_modal(request, record_id):
    """HTMX GET: confirmation copy + hidden hx-post form for edit-page status actions."""
    dental_record = get_object_or_404(DentalRecord, pk=record_id)
    to = (request.GET.get('to') or '').strip().lower()
    missing_consents = to == 'completed' and not dental_record.has_required_consents()
    unavailable = (
        to not in ('pending', 'completed')
        or (to == 'completed' and dental_record.status != 'pending')
        or to == 'pending'
        or missing_consents
    )
    context = {
        'dental_record': dental_record,
        'unavailable': unavailable,
        'missing_consents': missing_consents,
        'target_status': to,
        'post_url': reverse('dental_records:mark_record_completed', kwargs={'record_id': dental_record.id}),
    }
    return render(request, 'dental_records/_mark_status_modal_body.html', context)


@login_required
@role_required('doctor', 'admin')
def mark_record_completed(request, record_id):
    """Mark a dental record as completed; completed status is permanent (cannot revert to pending)."""
    edit_url = reverse('dental_records:dental_record_edit', kwargs={'record_id': record_id})
    is_htmx = request.headers.get('HX-Request') == 'true'

    if request.method != 'POST':
        return redirect(edit_url)

    dental_record = get_object_or_404(DentalRecord, pk=record_id)
    new_status = request.POST.get('status', 'completed')
    if new_status == 'completed' and not dental_record.has_required_consents():
        err = DentalRecord.CONSENTS_REQUIRED_FOR_COMPLETION
        if is_htmx:
            response = HttpResponse('', status=409)
            return htmx_add_toast(response, err, 'error')
        messages.error(request, err)
        return redirect(edit_url)

    if new_status not in ('pending', 'completed'):
        if is_htmx:
            response = HttpResponse('', status=400)
            return htmx_add_toast(response, 'Invalid status.', 'error')
        messages.error(request, 'Invalid status.')
        return redirect(edit_url)

    if new_status == 'pending':
        err = 'Completed dental records cannot be reverted.'
        if is_htmx:
            response = HttpResponse('', status=409)
            return htmx_add_toast(response, err, 'error')
        messages.error(request, err)
        return redirect(edit_url)

    appointment_marked_completed = False
    with transaction.atomic():
        locked = DentalRecord.objects.select_for_update().get(pk=dental_record.pk)
        if locked.status == 'completed':
            err = 'This dental record is already completed.'
            if is_htmx:
                response = HttpResponse('', status=409)
                return htmx_add_toast(response, err, 'error')
            messages.info(request, err)
            return redirect(edit_url)
        locked.status = new_status
        update_fields = ['status', 'updated_at']
        # Closing guest intake when the clinical record is completed (no longer awaiting).
        if (
            new_status == 'completed'
            and is_guest_user(locked.patient)
            and locked.intake_status != 'guest_submitted'
        ):
            locked.intake_status = 'guest_submitted'
            update_fields.append('intake_status')
        locked.save(update_fields=update_fields)

        if new_status == 'completed' and locked.appointment_id:
            apt = Appointment.objects.select_for_update().get(pk=locked.appointment_id)
            if apt.status != 'completed':
                apt.status = 'completed'
                apt.save(update_fields=['status'])
                appointment_marked_completed = True

    if new_status == 'completed':
        _audit_dental(request, dental_record, 'edit', section='status')
        if appointment_marked_completed:
            msg = 'Dental record and associated appointment marked as completed.'
        else:
            msg = 'Dental record marked as completed. The patient can now view their record.'

        dental_record = DentalRecord.objects.select_related(
            'appointment', 'appointment__doctor', 'appointment__patient', 'patient'
        ).get(pk=dental_record.pk)
        patient = dental_record.patient
        if patient:
            from core.guest_emails import (
                email_appointment_results_ready,
                email_guest_dental_record_results_ready,
            )
            from core.notification_delivery import notify_user

            visit_date = (
                dental_record.appointment.date.strftime('%B %d, %Y')
                if dental_record.appointment_id
                else 'your visit'
            )
            notify_user(
                patient,
                title='Dental Record Ready',
                message=f'Your dental record from {visit_date} is now available.',
                notification_type='general',
                transaction_type='appointment_completed',
                related_id=dental_record.appointment_id or dental_record.pk,
                send_email=False,
            )
            if is_guest_user(patient):
                emailed = email_guest_dental_record_results_ready(
                    request, dental_record, created_by=request.user
                )
                if emailed:
                    msg = f'{msg} Guest was emailed a view-only link.'
            elif dental_record.appointment_id:
                email_appointment_results_ready(
                    request, dental_record.appointment, created_by=request.user
                )

    if is_htmx:
        dr = DentalRecord.objects.select_related('appointment', 'patient').get(pk=record_id)
        get_params = _effective_dental_list_get_params(request)
        list_ctx = _build_dental_list_page_context(request, get_params=get_params)
        oob_html = render_to_string(
            'dental_records/_dr_post_status_oob.html',
            {
                'user': request.user,
                **list_ctx,
                **_dental_action_bar_context(dr),
            },
            request=request,
        )
        response = HttpResponse(oob_html, status=200)
        response = htmx_add_trigger(response, 'close-modal')
        return htmx_add_toast(response, msg, 'success')

    messages.success(request, msg)

    return redirect(edit_url)
