"""Login-exempt magic-link views for guest patients."""

from __future__ import annotations

from datetime import datetime as dt
from datetime import timedelta

from django.contrib import messages
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods

from appointments.models import Appointment
from health_forms_services.forms import (
    HealthProfileMedicalHistoryForm,
    HealthProfilePersonalInfoForm,
)
from health_forms_services.models import HealthProfileForm
from health_forms_services.services import PATIENT_HISTORY_SECTIONS, validate_submit_for_review

from .guest_access import mark_guest_token_used, revoke_guest_token, validate_guest_token
from .guest_auth import is_guest_user
from .academic_catalog import patient_catalog_context
from .models import GuestAccessToken, User
from .notification_delivery import notify_user
from .settings_service import get_clinic_settings


def _notify_clinic_guest_health_form_submitted(health_form, access_token):
    """Ping creating clinician, or health-profile module holders, when a guest submits."""
    patient_name = (
        health_form.get_full_name()
        or getattr(health_form.user, 'get_full_name', lambda: '')()
        or 'Guest'
    )
    title = 'Guest health form submitted'
    message = (
        f'{patient_name} submitted a health profile for clinical completion and review.'
    )
    recipients: list[User] = []
    created_by = getattr(access_token, 'created_by', None)
    if created_by and getattr(created_by, 'is_active', False) and not getattr(created_by, 'is_deleted', False):
        recipients = [created_by]
    else:
        from .doctor_access import MODULE_HEALTH_PROFILE_FORMS, has_clinical_module

        candidates = User.objects.filter(
            role__in=['staff', 'doctor', 'admin'],
            is_active=True,
            is_deleted=False,
        )
        recipients = [
            user
            for user in candidates
            if has_clinical_module(user, MODULE_HEALTH_PROFILE_FORMS)
        ]

    for recipient in recipients:
        notify_user(
            recipient,
            title=title,
            message=message,
            notification_type='general',
            transaction_type='health_form_incomplete',
            related_id=health_form.pk,
            send_email=False,
        )


def _require_guest_token(raw_token: str, purpose: str):
    token = validate_guest_token(raw_token, purpose)
    if not token:
        raise Http404('This link is invalid or has expired.')
    if not is_guest_user(token.user):
        raise Http404('This link is invalid or has expired.')
    return token


def _appointment_within_cancel_cutoff(appointment) -> tuple[bool, int]:
    cutoff_hours = get_clinic_settings().cancellation_cutoff_hours
    appt_start = timezone.make_aware(
        dt.combine(appointment.date, appointment.time),
        timezone.get_current_timezone(),
    )
    ok = timezone.now() + timedelta(hours=cutoff_hours) <= appt_start
    return ok, cutoff_hours


def _render_guest_appointment(request, appointment, access, token, *, just_cancelled=False):
    can_cancel = (
        not just_cancelled
        and appointment.status in ('pending', 'confirmed')
    )
    cutoff_ok, cutoff_hours = (True, 0)
    if can_cancel:
        cutoff_ok, cutoff_hours = _appointment_within_cancel_cutoff(appointment)
    return render(
        request,
        'core/guest/appointment_detail.html',
        {
            'appointment': appointment,
            'guest_token': token,
            'patient': access.user,
            'can_cancel': can_cancel and cutoff_ok,
            'cancel_blocked_by_cutoff': can_cancel and not cutoff_ok,
            'cancellation_cutoff_hours': cutoff_hours,
            'just_cancelled': just_cancelled,
        },
    )


@csrf_protect
@require_http_methods(['GET', 'POST'])
def guest_appointment(request, token):
    access = _require_guest_token(token, GuestAccessToken.Purpose.APPOINTMENT)
    appointment = get_object_or_404(
        Appointment.objects.select_related('patient', 'doctor'),
        pk=access.object_id,
        patient_id=access.user_id,
    )
    mark_guest_token_used(access)

    if request.method == 'POST' and (request.POST.get('action') or '').strip() == 'cancel':
        if appointment.status not in ('pending', 'confirmed'):
            messages.error(request, 'This appointment can no longer be cancelled.')
            return _render_guest_appointment(request, appointment, access, token)

        cutoff_ok, cutoff_hours = _appointment_within_cancel_cutoff(appointment)
        if not cutoff_ok:
            messages.error(
                request,
                f'Cancellations must be at least {cutoff_hours} hours before the appointment.',
            )
            return _render_guest_appointment(request, appointment, access, token)

        appointment.status = 'cancelled'
        appointment.save(update_fields=['status', 'updated_at'])
        notify_user(
            appointment.doctor,
            title='Appointment Cancelled',
            message=(
                f'Appointment with {access.user.get_full_name() or access.user.email} '
                f'has been cancelled by the patient.'
            ),
            notification_type='appointment',
            transaction_type='appointment_cancelled',
            related_id=appointment.id,
        )
        revoke_guest_token(access)
        messages.success(request, 'Your appointment has been cancelled.')
        return _render_guest_appointment(
            request, appointment, access, token, just_cancelled=True
        )

    return _render_guest_appointment(request, appointment, access, token)


def _guest_health_form_tabs():
    return [
        {'key': 'personal', 'label': 'Personal Info', 'icon': 'fa-user'},
        {'key': 'medical', 'label': 'Medical History', 'icon': 'fa-notes-medical'},
    ]


def _guest_form_class_map():
    return {
        'personal': HealthProfilePersonalInfoForm,
        'medical': HealthProfileMedicalHistoryForm,
    }


def _build_guest_section_form(form_class, *, instance, user, data=None):
    kwargs = {'instance': instance}
    if data is not None:
        kwargs['data'] = data
    try:
        return form_class(user=user, **kwargs)
    except TypeError:
        return form_class(**kwargs)


@csrf_protect
@require_http_methods(['GET', 'POST'])
def guest_health_form(request, token):
    access = _require_guest_token(token, GuestAccessToken.Purpose.HEALTH_FORM)
    health_form = get_object_or_404(
        HealthProfileForm.objects.select_related('user'),
        pk=access.object_id,
        user_id=access.user_id,
    )
    if health_form.status != HealthProfileForm.Status.INCOMPLETE:
        return render(
            request,
            'core/guest/health_form_closed.html',
            {
                'health_form': health_form,
                'patient': access.user,
            },
        )

    mark_guest_token_used(access)
    tabs = _guest_health_form_tabs()
    form_map = _guest_form_class_map()
    active_section = request.GET.get('section') or request.POST.get('section') or 'personal'
    if active_section not in PATIENT_HISTORY_SECTIONS:
        active_section = 'personal'

    guest_path = reverse('core:guest_health_form', kwargs={'token': token})

    if request.method == 'POST':
        action = (request.POST.get('action') or 'save').strip()
        if action == 'cancel':
            health_form.status = HealthProfileForm.Status.CANCELLED
            health_form.save(update_fields=['status', 'updated_at'])
            revoke_guest_token(access)
            messages.success(request, 'Your health form draft has been cancelled.')
            return render(
                request,
                'core/guest/health_form_closed.html',
                {
                    'health_form': health_form,
                    'patient': access.user,
                    'just_cancelled': True,
                },
            )
        if action == 'submit':
            errors = validate_submit_for_review(health_form)
            if errors:
                for err in errors:
                    messages.error(request, err)
                return redirect(f'{guest_path}?section={active_section}')
            health_form.status = HealthProfileForm.Status.PENDING
            health_form.save(update_fields=['status', 'updated_at'])
            _notify_clinic_guest_health_form_submitted(health_form, access)
            messages.success(request, 'Your health form was submitted for clinic review.')
            return render(
                request,
                'core/guest/health_form_closed.html',
                {
                    'health_form': health_form,
                    'patient': access.user,
                    'just_submitted': True,
                },
            )

        form_class = form_map.get(active_section)
        if not form_class:
            raise Http404('Unknown section.')
        section_form = _build_guest_section_form(
            form_class, instance=health_form, user=access.user, data=request.POST
        )
        if section_form.is_valid():
            saved = section_form.save(commit=False)
            saved.save()
            if active_section == 'personal':
                email = (section_form.cleaned_data.get('email_address') or '').strip()
                profile = getattr(access.user, 'patient_profile', None)
                if email and profile and profile.contact_email != email:
                    profile.contact_email = email
                    profile.save(update_fields=['contact_email'])
            messages.success(request, f'{active_section.capitalize()} section saved.')
            return redirect(f'{guest_path}?section={active_section}')
        form_instances = {
            key: (
                section_form
                if key == active_section
                else _build_guest_section_form(form_class_inner, instance=health_form, user=access.user)
            )
            for key, form_class_inner in form_map.items()
        }
    else:
        form_instances = {
            key: _build_guest_section_form(form_class, instance=health_form, user=access.user)
            for key, form_class in form_map.items()
        }
        section_form = form_instances[active_section]

    return render(
        request,
        'core/guest/health_form_edit.html',
        {
            'health_form': health_form,
            'patient': access.user,
            'guest_token': token,
            'tabs': tabs,
            'active_section': active_section,
            'form_instances': form_instances,
            'active_form': section_form if request.method == 'POST' else form_instances[active_section],
            'guest_path': guest_path,
            'can_submit_for_review': True,
            'can_cancel': True,
            **patient_catalog_context(),
        },
    )


@csrf_protect
@require_http_methods(['GET'])
def guest_medical_record(request, token):
    """Magic-link read-only view of a guest patient's medical record."""
    from medical_records.models import MedicalRecord

    access = _require_guest_token(token, GuestAccessToken.Purpose.MEDICAL_RECORD)
    medical_record = get_object_or_404(
        MedicalRecord.objects.select_related(
            'patient',
            'patient__patient_profile',
            'doctor',
            'doctor__staff_profile',
            'appointment',
            'prescription_record',
        ).prefetch_related('prescription_record__items'),
        pk=access.object_id,
        patient_id=access.user_id,
    )
    mark_guest_token_used(access)

    prescription_items = []
    from django.core.exceptions import ObjectDoesNotExist

    try:
        rx = medical_record.prescription_record
    except ObjectDoesNotExist:
        rx = None
    if rx is not None:
        prescription_items = list(rx.items.all())

    return render(
        request,
        'core/guest/medical_record_detail.html',
        {
            'medical_record': medical_record,
            'appointment': medical_record.appointment,
            'patient': access.user,
            'guest_token': token,
            'prescription_items': prescription_items,
        },
    )


def _guest_dental_record_context(dental_record):
    """Related clinical sections for guest dental detail views."""
    import json

    from dental_records.models import (
        DentalExamination,
        DentalVitalSigns,
        DentalHealthQuestionnaire,
        DentalSystemsReview,
        DentalHistory,
        PediatricDentalHistory,
    )

    try:
        examination = dental_record.examination
    except DentalExamination.DoesNotExist:
        examination = None
    try:
        vital_signs = dental_record.vital_signs
    except DentalVitalSigns.DoesNotExist:
        vital_signs = None
    try:
        health_questionnaire = dental_record.health_questionnaire
    except DentalHealthQuestionnaire.DoesNotExist:
        health_questionnaire = None
    try:
        systems_review = dental_record.systems_review
    except DentalSystemsReview.DoesNotExist:
        systems_review = None
    try:
        dental_history = dental_record.dental_history
    except DentalHistory.DoesNotExist:
        dental_history = None
    try:
        pediatric_history = dental_record.pediatric_history
    except PediatricDentalHistory.DoesNotExist:
        pediatric_history = None

    dental_chart = dental_record.dental_chart.all().prefetch_related('surfaces')
    dental_chart_json = []
    for tooth in dental_chart:
        surfaces_data = [
            {
                'id': surface.id,
                'surface': surface.surface,
                'condition': surface.condition,
                'notes': surface.notes,
            }
            for surface in tooth.surfaces.all()
        ]
        dental_chart_json.append({
            'id': tooth.id,
            'tooth_number': tooth.tooth_number,
            'tooth_type': tooth.tooth_type,
            'condition': tooth.condition,
            'notes': tooth.notes,
            'quadrant': tooth.fdi_quadrant,
            'quadrant_name': tooth.quadrant_name,
            'surfaces': surfaces_data,
        })

    return {
        'examination': examination,
        'vital_signs': vital_signs,
        'health_questionnaire': health_questionnaire,
        'systems_review': systems_review,
        'dental_history': dental_history,
        'pediatric_history': pediatric_history,
        'dental_chart': dental_chart,
        'dental_chart_json': json.dumps(dental_chart_json),
        'is_pediatric': bool(dental_record.age and dental_record.age < 18),
    }


@csrf_protect
@require_http_methods(['GET'])
def guest_dental_record(request, token):
    """Magic-link read-only view of a guest patient's completed dental record."""
    from dental_records.models import DentalRecord

    access = _require_guest_token(token, GuestAccessToken.Purpose.DENTAL_RECORD)
    dental_record = get_object_or_404(
        DentalRecord.objects.select_related(
            'patient',
            'patient__patient_profile',
            'examined_by',
            'appointment',
        ).prefetch_related('progress_notes', 'progress_notes__dentist'),
        pk=access.object_id,
        patient_id=access.user_id,
    )
    mark_guest_token_used(access)

    # Guests only see completed clinical results via this purpose.
    if dental_record.status != 'completed':
        raise Http404('This dental record is not available yet.')

    ctx = _guest_dental_record_context(dental_record)
    return render(
        request,
        'core/guest/dental_record_detail.html',
        {
            'dental_record': dental_record,
            'appointment': dental_record.appointment,
            'patient': access.user,
            'guest_token': token,
            **ctx,
        },
    )


def _notify_clinic_guest_dental_intake_submitted(dental_record, access_token):
    """Notify creating clinician (or dental module holders) when guest submits intake."""
    patient_name = (
        getattr(dental_record.patient, 'get_full_name', lambda: '')()
        or 'Guest'
    )
    title = 'Guest dental intake submitted'
    message = (
        f'{patient_name} submitted dental demographics and consent. '
        'Clinical sections can now be completed.'
    )
    recipients: list[User] = []
    created_by = getattr(access_token, 'created_by', None)
    if created_by and getattr(created_by, 'is_active', False) and not getattr(created_by, 'is_deleted', False):
        recipients = [created_by]
    else:
        from .doctor_access import MODULE_DENTAL_RECORDS, has_clinical_module

        candidates = User.objects.filter(
            role__in=['staff', 'doctor', 'admin'],
            is_active=True,
            is_deleted=False,
        )
        recipients = [
            user
            for user in candidates
            if has_clinical_module(user, MODULE_DENTAL_RECORDS)
        ]

    for recipient in recipients:
        notify_user(
            recipient,
            title=title,
            message=message,
            notification_type='general',
            transaction_type='general_announcement',
            related_id=dental_record.pk,
            send_email=False,
        )


@csrf_protect
@require_http_methods(['GET', 'POST'])
def guest_dental_intake(request, token):
    """Magic-link guest dental demographics + consent intake."""
    from dental_records.forms import GuestDentalIntakeForm
    from dental_records.models import DentalRecord

    access = _require_guest_token(token, GuestAccessToken.Purpose.DENTAL_INTAKE)
    dental_record = get_object_or_404(
        DentalRecord.objects.select_related('patient', 'patient__patient_profile'),
        pk=access.object_id,
        patient_id=access.user_id,
    )
    if dental_record.intake_status != 'awaiting_guest':
        return render(
            request,
            'core/guest/dental_intake_closed.html',
            {
                'dental_record': dental_record,
                'patient': access.user,
            },
        )

    mark_guest_token_used(access)
    guest_path = reverse('core:guest_dental_intake', kwargs={'token': token})

    def _apply_guest_defaults(saved):
        saved.patient = dental_record.patient
        saved.examined_by = dental_record.examined_by
        saved.appointment = dental_record.appointment
        saved.status = 'pending'
        saved.designation = 'student'
        saved.department_college_office = 'Guest'
        saved.course = ''
        saved.year_level = ''
        return saved

    if request.method == 'POST':
        action = (request.POST.get('action') or 'save').strip()
        is_submit = action == 'submit'
        form = GuestDentalIntakeForm(
            request.POST, instance=dental_record, draft=not is_submit
        )
        if form.is_valid():
            saved = _apply_guest_defaults(form.save(commit=False))
            if is_submit:
                saved.intake_status = 'guest_submitted'
                saved.save()
                _notify_clinic_guest_dental_intake_submitted(saved, access)
                messages.success(
                    request,
                    'Your dental intake was submitted. The clinic will complete the exam.',
                )
                return render(
                    request,
                    'core/guest/dental_intake_closed.html',
                    {
                        'dental_record': saved,
                        'patient': access.user,
                        'just_submitted': True,
                    },
                )
            saved.intake_status = 'awaiting_guest'
            saved.save()
            email = (form.cleaned_data.get('email') or '').strip()
            profile = getattr(access.user, 'patient_profile', None)
            if email and profile and profile.contact_email != email:
                profile.contact_email = email
                profile.save(update_fields=['contact_email'])
            messages.success(request, 'Your details were saved. Submit when you are ready.')
            return redirect(guest_path)
    else:
        form = GuestDentalIntakeForm(instance=dental_record)

    return render(
        request,
        'core/guest/dental_intake_edit.html',
        {
            'dental_record': dental_record,
            'patient': access.user,
            'guest_token': token,
            'form': form,
            'guest_path': guest_path,
        },
    )
