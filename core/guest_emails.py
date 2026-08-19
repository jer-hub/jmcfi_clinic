"""Outbound emails for guest and patient appointment / health-form flows."""

from __future__ import annotations

import logging

from django.conf import settings
from django.urls import reverse

from .guest_access import build_guest_url, issue_guest_access_token
from .guest_auth import is_guest_user, resolve_patient_contact_email
from .models import GuestAccessToken
from .notification_delivery import send_templated_email

logger = logging.getLogger(__name__)


def _absolute_url(request, path: str) -> str:
    if request is not None:
        try:
            return request.build_absolute_uri(path)
        except Exception:
            logger.warning('build_absolute_uri failed; falling back to SITE_URL', exc_info=True)
    site_url = (getattr(settings, 'SITE_URL', None) or '').rstrip('/')
    if site_url:
        return f'{site_url}{path}'
    return path


def email_guest_appointment_scheduled(request, appointment, *, created_by=None) -> bool:
    """Issue magic link and email guest patient about a scheduled appointment."""
    patient = appointment.patient
    if not is_guest_user(patient):
        return False
    if not resolve_patient_contact_email(patient):
        return False

    _, raw = issue_guest_access_token(
        patient,
        GuestAccessToken.Purpose.APPOINTMENT,
        appointment.pk,
        created_by=created_by,
    )
    link = build_guest_url(request, GuestAccessToken.Purpose.APPOINTMENT, raw)
    doctor_name = appointment.doctor.get_full_name() or appointment.doctor.email
    return send_templated_email(
        patient,
        'Appointment scheduled',
        'core/email/guest_appointment_scheduled',
        {
            'appointment': appointment,
            'doctor_name': doctor_name,
            'access_url': link,
            'patient_name': patient.get_full_name() or 'Patient',
        },
        raise_on_error=True,
    )


_STATUS_SUBJECTS = {
    'confirmed': 'Appointment confirmed',
    'pending': 'Appointment update',
    'cancelled': 'Appointment cancelled',
    'missed': 'Appointment missed',
}

_STATUS_INTRO = {
    'confirmed': 'Your appointment has been confirmed.',
    'pending': 'Your appointment status is now Pending.',
    'cancelled': 'Your appointment has been cancelled.',
    'missed': 'You missed your scheduled appointment.',
}


def _status_display_label(status_code: str | None) -> str:
    if not status_code:
        return ''
    from appointments.models import Appointment

    return dict(Appointment.STATUS_CHOICES).get(
        status_code,
        status_code.replace('_', ' ').title(),
    )


def _appointment_update_email_context(
    appointment,
    *,
    access_url: str,
    previous_status: str | None = None,
) -> dict:
    patient = appointment.patient
    status = appointment.status
    return {
        'appointment': appointment,
        'doctor_name': appointment.doctor.get_full_name() or appointment.doctor.email,
        'access_url': access_url,
        'patient_name': patient.get_full_name() or 'Patient',
        'status_label': appointment.get_status_display(),
        'previous_status': previous_status,
        'previous_status_label': _status_display_label(previous_status),
        'intro_line': _STATUS_INTRO.get(
            status,
            f'Your appointment status is now {appointment.get_status_display()}.',
        ),
        'cta_label': 'View appointment details',
    }


def email_guest_appointment_updated(
    request,
    appointment,
    *,
    previous_status: str | None = None,
    created_by=None,
) -> bool:
    """Issue magic link and email guest about an appointment status update."""
    patient = appointment.patient
    if not is_guest_user(patient):
        return False
    if not resolve_patient_contact_email(patient):
        return False

    _, raw = issue_guest_access_token(
        patient,
        GuestAccessToken.Purpose.APPOINTMENT,
        appointment.pk,
        created_by=created_by,
    )
    link = build_guest_url(request, GuestAccessToken.Purpose.APPOINTMENT, raw)
    subject = _STATUS_SUBJECTS.get(appointment.status, 'Appointment update')
    return send_templated_email(
        patient,
        subject,
        'core/email/guest_appointment_updated',
        _appointment_update_email_context(
            appointment,
            access_url=link,
            previous_status=previous_status,
        ),
        raise_on_error=True,
    )


def email_patient_appointment_updated(
    request,
    appointment,
    *,
    previous_status: str | None = None,
) -> bool:
    """Email a registered patient about an appointment status update."""
    patient = appointment.patient
    if is_guest_user(patient):
        return False
    if not resolve_patient_contact_email(patient):
        return False

    path = reverse('appointments:appointment_detail', kwargs={'appointment_id': appointment.pk})
    link = _absolute_url(request, path)
    subject = _STATUS_SUBJECTS.get(appointment.status, 'Appointment update')
    return send_templated_email(
        patient,
        subject,
        'core/email/patient_appointment_updated',
        _appointment_update_email_context(
            appointment,
            access_url=link,
            previous_status=previous_status,
        ),
        raise_on_error=True,
    )


def email_appointment_updated(
    request,
    appointment,
    *,
    previous_status: str | None = None,
    created_by=None,
) -> bool:
    """Route appointment status-update email: guest magic link vs patient detail page."""
    patient = appointment.patient
    if is_guest_user(patient):
        return email_guest_appointment_updated(
            request,
            appointment,
            previous_status=previous_status,
            created_by=created_by,
        )
    return email_patient_appointment_updated(
        request,
        appointment,
        previous_status=previous_status,
    )


def email_patient_appointment_scheduled(request, appointment) -> bool:
    """
    Email an existing (signed-in) patient with appointment details and a link
    to the clinic appointment page (login required if not already signed in).
    """
    patient = appointment.patient
    if is_guest_user(patient):
        return False
    if not resolve_patient_contact_email(patient):
        return False

    path = reverse('appointments:appointment_detail', kwargs={'appointment_id': appointment.pk})
    link = _absolute_url(request, path)
    doctor_name = appointment.doctor.get_full_name() or appointment.doctor.email
    return send_templated_email(
        patient,
        'Appointment scheduled',
        'core/email/patient_appointment_scheduled',
        {
            'appointment': appointment,
            'doctor_name': doctor_name,
            'access_url': link,
            'patient_name': patient.get_full_name() or 'Patient',
        },
        raise_on_error=True,
    )


def _appointment_detail_url(request, appointment) -> str:
    path = reverse('appointments:appointment_detail', kwargs={'appointment_id': appointment.pk})
    return _absolute_url(request, path)


def _doctor_appointment_email_context(
    appointment,
    access_url: str,
    *,
    cancelled_by=None,
) -> dict:
    doctor = appointment.doctor
    patient = appointment.patient
    ctx = {
        'appointment': appointment,
        'doctor_name': (doctor.get_full_name() or doctor.email) if doctor else '',
        'patient_name': patient.get_full_name() or getattr(patient, 'email', '') or 'Patient',
        'access_url': access_url,
    }
    if cancelled_by is not None:
        ctx['cancelled_by_name'] = (
            cancelled_by.get_full_name() or getattr(cancelled_by, 'email', '') or 'Clinic staff'
        )
    return ctx


def email_doctor_new_appointment_request(request, appointment) -> bool:
    """
    Email the assigned doctor when a patient books an appointment, with full
    details and a link to the appointment detail page.
    """
    doctor = appointment.doctor
    if not doctor or not resolve_patient_contact_email(doctor):
        return False

    return send_templated_email(
        doctor,
        'New appointment request',
        'core/email/doctor_appointment_request',
        _doctor_appointment_email_context(appointment, _appointment_detail_url(request, appointment)),
        raise_on_error=False,
    )


def email_doctor_appointment_cancelled(
    request,
    appointment,
    *,
    cancelled_by=None,
) -> bool:
    """Email the assigned doctor when an appointment is cancelled."""
    doctor = appointment.doctor
    if not doctor or not resolve_patient_contact_email(doctor):
        return False

    return send_templated_email(
        doctor,
        'Appointment cancelled',
        'core/email/doctor_appointment_cancelled',
        _doctor_appointment_email_context(
            appointment,
            _appointment_detail_url(request, appointment),
            cancelled_by=cancelled_by,
        ),
        raise_on_error=False,
    )


def _appointment_result_access(appointment) -> tuple[str, str]:
    """
    Prefer a clinical record URL when available; otherwise appointment detail.
    Returns (path, result_kind_label).
    """
    medical = appointment.medicalrecord_set.order_by('-id').first()
    if medical:
        return (
            reverse('medical_records:medical_record_detail_page', kwargs={'record_id': medical.pk}),
            'medical record',
        )
    dental = appointment.dental_records.order_by('-id').first()
    if dental:
        return (
            reverse('dental_records:dental_record_detail', kwargs={'record_id': dental.pk}),
            'dental record',
        )
    return (
        reverse('appointments:appointment_detail', kwargs={'appointment_id': appointment.pk}),
        'appointment summary',
    )


def email_patient_appointment_results_ready(request, appointment) -> bool:
    """
    Email an existing patient that visit results are ready, with a login-required link
    to their medical/dental record or appointment page.
    """
    patient = appointment.patient
    if is_guest_user(patient):
        return False
    if not resolve_patient_contact_email(patient):
        return False

    path, result_kind = _appointment_result_access(appointment)
    link = _absolute_url(request, path)
    doctor_name = appointment.doctor.get_full_name() or appointment.doctor.email
    return send_templated_email(
        patient,
        'Your appointment results are ready',
        'core/email/patient_appointment_results_ready',
        {
            'appointment': appointment,
            'doctor_name': doctor_name,
            'access_url': link,
            'result_kind': result_kind,
            'patient_name': patient.get_full_name() or 'Patient',
        },
        raise_on_error=False,
    )


def email_guest_medical_record_results_ready(request, medical_record, *, created_by=None) -> bool:
    """Issue magic link and email guest patient to view a medical record."""
    patient = medical_record.patient
    if not is_guest_user(patient):
        return False
    if not resolve_patient_contact_email(patient):
        return False

    _, raw = issue_guest_access_token(
        patient,
        GuestAccessToken.Purpose.MEDICAL_RECORD,
        medical_record.pk,
        created_by=created_by,
    )
    link = build_guest_url(request, GuestAccessToken.Purpose.MEDICAL_RECORD, raw)
    doctor = getattr(medical_record, 'doctor', None)
    doctor_name = ''
    if doctor:
        doctor_name = doctor.get_full_name() or doctor.email
    appointment = getattr(medical_record, 'appointment', None)
    return send_templated_email(
        patient,
        'Your medical record results are ready',
        'core/email/guest_medical_record_results_ready',
        {
            'medical_record': medical_record,
            'appointment': appointment,
            'doctor_name': doctor_name,
            'access_url': link,
            'patient_name': patient.get_full_name() or 'Patient',
        },
        raise_on_error=False,
    )


def email_patient_medical_record_results_ready(request, medical_record) -> bool:
    """
    Email a registered patient that their medical record is ready, with a
    login-required link to the medical record detail page.
    """
    patient = medical_record.patient
    if is_guest_user(patient):
        return False
    if not resolve_patient_contact_email(patient):
        return False

    path = reverse(
        'medical_records:medical_record_detail_page',
        kwargs={'record_id': medical_record.pk},
    )
    link = _absolute_url(request, path)
    doctor = getattr(medical_record, 'doctor', None)
    doctor_name = ''
    if doctor:
        doctor_name = doctor.get_full_name() or doctor.email
    appointment = getattr(medical_record, 'appointment', None)
    return send_templated_email(
        patient,
        'Your medical record is ready',
        'core/email/patient_medical_record_results_ready',
        {
            'medical_record': medical_record,
            'appointment': appointment,
            'doctor_name': doctor_name,
            'access_url': link,
            'patient_name': patient.get_full_name() or 'Patient',
        },
        raise_on_error=False,
    )


def email_medical_record_results_ready(request, medical_record, *, created_by=None) -> bool:
    """Route medical-record results email: guest magic link vs patient detail page."""
    patient = medical_record.patient
    if is_guest_user(patient):
        return email_guest_medical_record_results_ready(
            request, medical_record, created_by=created_by
        )
    return email_patient_medical_record_results_ready(request, medical_record)


def email_guest_dental_record_results_ready(request, dental_record, *, created_by=None) -> bool:
    """Issue magic link and email guest patient to view a completed dental record."""
    patient = dental_record.patient
    if not is_guest_user(patient):
        return False
    if not resolve_patient_contact_email(patient):
        return False

    _, raw = issue_guest_access_token(
        patient,
        GuestAccessToken.Purpose.DENTAL_RECORD,
        dental_record.pk,
        created_by=created_by,
    )
    link = build_guest_url(request, GuestAccessToken.Purpose.DENTAL_RECORD, raw)
    doctor = getattr(dental_record, 'examined_by', None)
    doctor_name = ''
    if doctor:
        doctor_name = doctor.get_full_name() or doctor.email
    appointment = getattr(dental_record, 'appointment', None)
    return send_templated_email(
        patient,
        'Your dental record results are ready',
        'core/email/guest_dental_record_results_ready',
        {
            'dental_record': dental_record,
            'appointment': appointment,
            'doctor_name': doctor_name,
            'access_url': link,
            'patient_name': patient.get_full_name() or 'Patient',
        },
        raise_on_error=False,
    )


def email_appointment_results_ready(request, appointment, *, created_by=None) -> bool:
    """
    Send results-ready email for an appointment: magic link for guests when a
    medical or dental record exists; login link for registered patients.
    """
    patient = appointment.patient
    if is_guest_user(patient):
        medical = appointment.medicalrecord_set.order_by('-id').first()
        if medical:
            return email_guest_medical_record_results_ready(
                request, medical, created_by=created_by
            )
        dental = appointment.dental_records.order_by('-id').first()
        if dental:
            return email_guest_dental_record_results_ready(
                request, dental, created_by=created_by
            )
        return False
    return email_patient_appointment_results_ready(request, appointment)


def email_guest_health_form_pending(request, health_form, *, created_by=None) -> bool:
    """Issue magic link and email guest patient to complete an incomplete health form."""
    patient = health_form.user
    if not is_guest_user(patient):
        return False
    if not resolve_patient_contact_email(patient):
        return False

    _, raw = issue_guest_access_token(
        patient,
        GuestAccessToken.Purpose.HEALTH_FORM,
        health_form.pk,
        created_by=created_by,
    )
    link = build_guest_url(request, GuestAccessToken.Purpose.HEALTH_FORM, raw)
    return send_templated_email(
        patient,
        'Complete your health profile form',
        'core/email/guest_health_form_pending',
        {
            'health_form': health_form,
            'access_url': link,
            'patient_name': patient.get_full_name() or 'Patient',
        },
        raise_on_error=True,
    )


def email_guest_dental_intake_pending(request, dental_record, *, created_by=None) -> bool:
    """Issue magic link and email guest to complete dental demographics + consent."""
    patient = dental_record.patient
    if not is_guest_user(patient):
        return False
    if not resolve_patient_contact_email(patient):
        return False

    _, raw = issue_guest_access_token(
        patient,
        GuestAccessToken.Purpose.DENTAL_INTAKE,
        dental_record.pk,
        created_by=created_by,
    )
    link = build_guest_url(request, GuestAccessToken.Purpose.DENTAL_INTAKE, raw)
    return send_templated_email(
        patient,
        'Complete your dental intake form',
        'core/email/guest_dental_intake_pending',
        {
            'dental_record': dental_record,
            'access_url': link,
            'patient_name': patient.get_full_name() or 'Patient',
        },
        raise_on_error=True,
    )


def email_patient_health_form_pending(request, health_form) -> bool:
    """
    Email an existing patient to finish demographics/history on an incomplete
    health profile (login-required edit link).
    """
    patient = health_form.user
    if is_guest_user(patient):
        return False
    if not resolve_patient_contact_email(patient):
        return False

    path = reverse('health_forms_services:edit_form', kwargs={'pk': health_form.pk})
    link = _absolute_url(request, path)
    return send_templated_email(
        patient,
        'Complete your health profile form',
        'core/email/patient_health_form_pending',
        {
            'health_form': health_form,
            'access_url': link,
            'patient_name': patient.get_full_name() or 'Patient',
        },
        raise_on_error=True,
    )
