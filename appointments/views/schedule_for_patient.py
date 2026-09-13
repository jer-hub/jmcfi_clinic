"""Staff/doctor schedule-for-patient views."""

from urllib.parse import urlencode
import json

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone

from appointments.appointment_utils import (
    check_appointment_availability,
    format_conflict_message,
)
from appointments.models import Appointment, AppointmentTypeDefault
from core.decorators import role_required
from core.notification_delivery import notify_user
from core.roles import PATIENT_ROLE_VALUES, ROLE_DOCTOR, ROLE_STAFF, role_matches

from .helpers import _get_schedule_context, _validate_assigned_doctor_for_type

User = get_user_model()


def _patient_prefill_payload(patient):
    """JSON-serializable patient row for schedule-for-patient Alpine prefill."""
    from core.utils import student_display_name

    profile = getattr(patient, 'patient_profile', None)
    patient_id = getattr(profile, 'patient_id', '') or ''
    return {
        'id': patient.id,
        'name': student_display_name(patient),
        'email': patient.email or '',
        'patient_id': patient_id,
        'course': getattr(profile, 'course', '') or '',
        'year_level': str(getattr(profile, 'year_level', '') or ''),
    }


def _schedule_for_patient_redirect(patient_id=None):
    base = reverse('appointments:schedule_for_patient')
    if patient_id:
        return redirect(f'{base}?{urlencode({"patient": patient_id})}')
    return redirect(base)


def _schedule_for_patient_patient_param(request, patient_id_hint=None):
    """Resolve patient id from POST hint, ?patient=, or legacy ?student=."""
    if patient_id_hint is not None:
        return patient_id_hint
    return request.GET.get('patient') or request.GET.get('student')


def _active_appointment_type_choices(user=None):
    """Active appointment types; doctors only see types they are assigned to."""
    defaults = AppointmentTypeDefault.objects.filter(is_active=True)
    if user is not None and role_matches(getattr(user, 'role', None), ROLE_DOCTOR):
        defaults = defaults.filter(assigned_doctors=user)
    active_type_keys = list(
        defaults.order_by('appointment_type').values_list('appointment_type', flat=True)
    )
    labels = dict(Appointment.APPOINTMENT_TYPE_CHOICES)
    return [(key, labels.get(key, key)) for key in active_type_keys]


def _schedule_for_patient_get_context(request, patient_id_hint=None, form_data=None):
    appointment_types = _active_appointment_type_choices(request.user)

    prefill_patient = None
    prefill_invalid = False
    url_patient_param = request.GET.get('patient') or request.GET.get('student')
    post_book_again = request.method == 'POST' and request.POST.get('book_again') == '1'
    book_again = bool(url_patient_param) or post_book_again
    resolve_param = patient_id_hint if patient_id_hint is not None else url_patient_param
    if resolve_param:
        try:
            patient = User.objects.select_related('patient_profile').get(
                pk=int(resolve_param),
                role__in=PATIENT_ROLE_VALUES,
            )
            prefill_patient = _patient_prefill_payload(patient)
        except (User.DoesNotExist, ValueError, TypeError):
            prefill_invalid = bool(url_patient_param)

    fd = form_data or {}
    context = {
        'appointment_types': appointment_types,
        'prefill_patient': prefill_patient,
        'prefill_invalid': prefill_invalid,
        'patient_locked': book_again and prefill_patient is not None,
        'staff_picks_doctor': request.user.role == ROLE_STAFF,
        'form_data': fd,
        'form_data_json': json.dumps(fd),
    }
    if request.user.role == ROLE_STAFF:
        context.update(_get_schedule_context(form_data=form_data, doctors_only=True))
    return context


def _schedule_guest_form_fields(post):
    """Persist guest draft fields after a failed schedule POST."""
    return {
        'register_guest': '1' if post.get('register_guest') == '1' else '',
        'guest_first_name': (post.get('guest_first_name') or '').strip(),
        'guest_last_name': (post.get('guest_last_name') or '').strip(),
        'guest_email': (post.get('guest_email') or '').strip(),
        'guest_phone': (post.get('guest_phone') or '').strip(),
    }


def _parse_schedule_guest_post(post):
    """Return (create_guest_user kwargs, error_message) for deferred guest booking."""
    from django.core.exceptions import ValidationError as DjangoValidationError
    from django.core.validators import validate_email

    from core.utils import clean_philippine_phone

    first_name = (post.get('guest_first_name') or '').strip()
    last_name = (post.get('guest_last_name') or '').strip()
    contact_email = (post.get('guest_email') or '').strip()
    phone_raw = (post.get('guest_phone') or '').strip()
    if not first_name or not last_name:
        return None, 'First and last name are required for guest registration.'
    if not contact_email:
        return None, 'A contact email is required for guest registration.'
    try:
        validate_email(contact_email)
    except DjangoValidationError:
        return None, 'Enter a valid contact email for the guest patient.'

    phone = None
    if phone_raw:
        try:
            phone = clean_philippine_phone(phone_raw)
        except DjangoValidationError:
            return None, 'Enter a valid 10-digit mobile number, or leave it blank.'

    return {
        'first_name': first_name,
        'last_name': last_name,
        'contact_email': contact_email,
        'phone': phone,
    }, None


def _render_schedule_for_patient(request, patient_id_hint=None, form_data=None):
    context = _schedule_for_patient_get_context(request, patient_id_hint=patient_id_hint, form_data=form_data)
    return render(request, 'appointments/schedule_for_patient.html', context)


@login_required
@role_required('doctor', 'staff', 'admin')
def schedule_for_patient(request):
    """Allows staff and doctors to schedule an appointment for a patient."""
    staff_picks_doctor = request.user.role == ROLE_STAFF

    if request.method == 'POST':
        patient_id = request.POST.get('patient')
        appointment_type = request.POST.get('appointment_type')
        date_str = request.POST.get('date')
        time_str = request.POST.get('time')
        reason = request.POST.get('reason')
        doctor_id = request.POST.get('doctor') if staff_picks_doctor else None
        registering_guest = request.POST.get('register_guest') == '1'
        guest_kwargs = None

        form_data = {
            'patient': '' if registering_guest else (patient_id or ''),
            'appointment_type': appointment_type or '',
            'date': date_str or '',
            'time': time_str or '',
            'reason': reason or '',
            'doctor': doctor_id or '',
        }
        form_data.update(_schedule_guest_form_fields(request.POST))

        if registering_guest:
            guest_kwargs, guest_err = _parse_schedule_guest_post(request.POST)
            if guest_err:
                messages.error(request, guest_err)
                return _render_schedule_for_patient(request, form_data=form_data)
            patient_id = ''

        required = [appointment_type, date_str, time_str, reason]
        if not registering_guest:
            required.append(patient_id)
        if staff_picks_doctor:
            required.append(doctor_id)

        if not all(required):
            messages.error(request, 'All fields are required.')
            return _render_schedule_for_patient(
                request,
                patient_id_hint=patient_id or None,
                form_data=form_data,
            )

        try:
            if staff_picks_doctor:
                doctor = User.objects.get(id=doctor_id, role=ROLE_DOCTOR, is_active=True)
            else:
                doctor = request.user
            from datetime import datetime
            appointment_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            appointment_time = datetime.strptime(time_str, '%H:%M').time()

            if appointment_date < timezone.now().date():
                messages.error(request, 'Cannot schedule appointments for past dates.')
                return _render_schedule_for_patient(
                    request, patient_id_hint=patient_id or None, form_data=form_data
                )

            if appointment_date.weekday() >= 5:
                messages.error(request, 'Appointments are not available on weekends.')
                return _render_schedule_for_patient(
                    request, patient_id_hint=patient_id or None, form_data=form_data
                )

            if staff_picks_doctor or role_matches(request.user.role, ROLE_DOCTOR):
                is_valid, err_msg = _validate_assigned_doctor_for_type(doctor, appointment_type)
                if not is_valid:
                    messages.error(request, err_msg)
                    return _render_schedule_for_patient(
                        request, patient_id_hint=patient_id or None, form_data=form_data
                    )
            else:
                type_default = AppointmentTypeDefault.objects.filter(
                    appointment_type=appointment_type, is_active=True
                ).first()
                if not type_default and AppointmentTypeDefault.objects.filter(appointment_type=appointment_type).exists():
                    messages.error(request, 'This appointment type is currently inactive.')
                    return _render_schedule_for_patient(
                        request, patient_id_hint=patient_id or None, form_data=form_data
                    )

            is_available, conflicts = check_appointment_availability(doctor, appointment_date, appointment_time)
            if not is_available:
                conflict_msg = format_conflict_message(doctor, conflicts)
                messages.error(request, conflict_msg)
                return _render_schedule_for_patient(
                    request, patient_id_hint=patient_id or None, form_data=form_data
                )

            patient = None
            if not registering_guest:
                patient = User.objects.get(id=patient_id, role__in=PATIENT_ROLE_VALUES)
                patient_conflict = Appointment.objects.filter(
                    patient=patient,
                    date=appointment_date,
                    time=appointment_time,
                    status__in=['pending', 'confirmed']
                ).exists()
                if patient_conflict:
                    messages.error(request, f'{patient.get_full_name()} already has a pending or confirmed appointment at this time.')
                    return _render_schedule_for_patient(
                        request, patient_id_hint=patient_id, form_data=form_data
                    )

            with transaction.atomic():
                if registering_guest:
                    from core.guest_auth import create_guest_user

                    patient = create_guest_user(**guest_kwargs)
                appointment = Appointment.objects.create(
                    patient=patient,
                    doctor=doctor,
                    appointment_type=appointment_type,
                    date=appointment_date,
                    time=appointment_time,
                    reason=reason,
                    status='confirmed',
                )

            # Ensure profile (contact_email) is available for guest delivery.
            patient = User.objects.select_related('patient_profile').get(pk=patient.pk)
            appointment.patient = patient

            from django.conf import settings as dj_settings
            from core.guest_emails import (
                email_guest_appointment_scheduled,
                email_patient_appointment_scheduled,
            )
            from core.notification_delivery import format_email_send_error
            from core.guest_auth import is_guest_user, resolve_patient_contact_email

            contact = resolve_patient_contact_email(patient)
            emailed = False
            email_error = ''

            if is_guest_user(patient):
                try:
                    emailed = email_guest_appointment_scheduled(
                        request, appointment, created_by=request.user
                    )
                except Exception as email_exc:
                    email_error = format_email_send_error(email_exc)
                    emailed = False
            else:
                # In-app only here; details + appointment URL go in the templated email.
                notify_user(
                    patient,
                    title='Appointment Scheduled for You',
                    message=(
                        f'Dr. {doctor.get_full_name()} has scheduled a new appointment for you on '
                        f'{appointment_date.strftime("%B %d, %Y")} at '
                        f'{appointment_time.strftime("%I:%M %p")}.'
                    ),
                    notification_type='appointment',
                    transaction_type='appointment_scheduled',
                    related_id=appointment.id,
                    send_email=False,
                )
                try:
                    emailed = email_patient_appointment_scheduled(request, appointment)
                except Exception as email_exc:
                    email_error = format_email_send_error(email_exc)
                    emailed = False

            if is_guest_user(patient) and not contact:
                messages.warning(
                    request,
                    'Appointment scheduled, but this guest has no contact email — the patient was not emailed.',
                )
            elif emailed:
                msg = f'Confirmation email sent to {contact}.'
                if 'console' in (dj_settings.EMAIL_BACKEND or ''):
                    msg += ' (Dev: EMAIL_BACKEND is console — message is printed in the server terminal, not delivered to an inbox.)'
                messages.success(request, msg)
            elif not emailed:
                detail = email_error or 'check clinic email settings / EMAIL_BACKEND'
                if is_guest_user(patient) or contact:
                    messages.warning(
                        request,
                        f'Appointment scheduled, but the confirmation email was not sent ({detail}).',
                    )

            messages.success(request, f'Appointment successfully scheduled for {patient.get_full_name()}.')
            return redirect('appointments:appointment_list')

        except User.DoesNotExist:
            messages.error(request, 'Invalid patient or doctor selected.')
        except ValueError:
            messages.error(request, 'Invalid date or time format.')
        except Exception as e:
            messages.error(request, f'An error occurred: {e}')

        return _render_schedule_for_patient(
            request,
            patient_id_hint=patient_id or None,
            form_data=form_data,
        )

    return _render_schedule_for_patient(request)
