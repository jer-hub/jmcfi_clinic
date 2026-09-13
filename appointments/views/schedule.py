"""Patient self-schedule and slot availability views."""

from datetime import timedelta
import logging

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date

from appointments.appointment_utils import (
    check_appointment_availability,
    classify_clinic_time_slots,
    format_conflict_message,
)
from appointments.models import Appointment, AppointmentTypeDefault
from core.decorators import role_required
from core.notification_delivery import notify_user
from core.roles import PATIENT_ROLE_VALUES, ROLE_DOCTOR, ROLE_PATIENT, role_matches
from core.settings_service import get_clinic_settings

from .helpers import _get_schedule_context, _validate_assigned_doctor_for_type

User = get_user_model()
logger = logging.getLogger(__name__)


@login_required
def schedule_appointment(request):
    if not role_matches(request.user.role, ROLE_PATIENT):
        messages.error(request, 'Only patients can schedule appointments')
        return redirect('core:dashboard')

    form_data = {}

    if request.method == 'POST':
        doctor_id = request.POST.get('doctor')
        appointment_type = request.POST.get('appointment_type')
        date = request.POST.get('date')
        time = request.POST.get('time')
        reason = request.POST.get('reason', '').strip()

        form_data = {
            'doctor': doctor_id or '',
            'appointment_type': appointment_type or '',
            'date': date or '',
            'time': time or '',
            'reason': reason,
        }

        if not all([doctor_id, appointment_type, date, time, reason]):
            messages.error(request, 'All fields are required.')
            return render(request, 'appointments/schedule_appointment.html',
                          _get_schedule_context(form_data=form_data))

        try:
            from datetime import datetime
            appointment_date = datetime.strptime(date, '%Y-%m-%d').date()
            appointment_time = datetime.strptime(time, '%H:%M').time()

            if appointment_date < timezone.now().date():
                messages.error(request, 'Cannot schedule appointments for past dates.')
                return render(request, 'appointments/schedule_appointment.html',
                              _get_schedule_context(form_data=form_data))

            max_days = get_clinic_settings().max_advance_booking_days
            from datetime import timedelta

            latest_date = timezone.now().date() + timedelta(days=max_days)
            if appointment_date > latest_date:
                messages.error(
                    request,
                    f'Appointments can only be booked up to {max_days} days in advance.',
                )
                return render(request, 'appointments/schedule_appointment.html',
                              _get_schedule_context(form_data=form_data))

            if appointment_date.weekday() >= 5:
                messages.error(request, 'Appointments are not available on weekends.')
                return render(request, 'appointments/schedule_appointment.html',
                              _get_schedule_context(form_data=form_data))

            doctor = User.objects.get(id=doctor_id, role='doctor', is_active=True)

            type_default = AppointmentTypeDefault.objects.filter(
                appointment_type=appointment_type, is_active=True
            ).prefetch_related('assigned_doctors').first()
            if not type_default:
                if AppointmentTypeDefault.objects.filter(appointment_type=appointment_type).exists():
                    messages.error(request, 'This appointment type is currently inactive.')
                else:
                    messages.error(request, 'Invalid appointment type selected.')
                return render(request, 'appointments/schedule_appointment.html',
                              _get_schedule_context(form_data=form_data))

            is_valid, err_msg = _validate_assigned_doctor_for_type(doctor, appointment_type)
            if not is_valid:
                messages.error(request, err_msg)
                return render(request, 'appointments/schedule_appointment.html',
                              _get_schedule_context(form_data=form_data))

            is_available, conflicts = check_appointment_availability(doctor, appointment_date, appointment_time)

            if not is_available:
                conflict_msg = format_conflict_message(doctor, conflicts)
                messages.error(request, conflict_msg)
                return render(request, 'appointments/schedule_appointment.html',
                              _get_schedule_context(form_data=form_data))

            appointment = Appointment.objects.create(
                patient=request.user,
                doctor=doctor,
                appointment_type=appointment_type,
                date=appointment_date,
                time=appointment_time,
                reason=reason
            )

            notify_user(
                doctor,
                title='New Appointment Request',
                message=(
                    f'New appointment request from {request.user.get_full_name()} for '
                    f'{appointment_date.strftime("%B %d, %Y")} at {appointment_time.strftime("%I:%M %p")}'
                ),
                notification_type='appointment',
                transaction_type='appointment_scheduled',
                related_id=appointment.id,
                send_email=False,
            )

            try:
                from core.guest_emails import (
                    email_doctor_new_appointment_request,
                    email_patient_appointment_scheduled,
                )

                email_doctor_new_appointment_request(request, appointment)
            except Exception:
                logger.warning(
                    'Doctor new appointment request email failed',
                    exc_info=True,
                )
            try:
                from core.guest_emails import email_patient_appointment_scheduled

                email_patient_appointment_scheduled(request, appointment)
            except Exception:
                logger.warning(
                    'Patient self-schedule confirmation email failed',
                    exc_info=True,
                )

            messages.success(request, 'Appointment scheduled successfully!')
            return redirect('appointments:appointment_list')

        except User.DoesNotExist:
            messages.error(request, 'Invalid doctor selected.')
        except ValueError:
            messages.error(request, 'Invalid date or time format.')
        except Exception:
            messages.error(request, 'An error occurred while scheduling the appointment. Please try again.')

        return render(request, 'appointments/schedule_appointment.html',
                      _get_schedule_context(form_data=form_data))

    initial_form: dict[str, str] = {}
    prefill_date = parse_date(request.GET.get('date', ''))
    if prefill_date:
        initial_form['date'] = prefill_date.isoformat()
    return render(request, 'appointments/schedule_appointment.html', _get_schedule_context(form_data=initial_form))


@login_required
@role_required('student', 'staff', 'doctor', 'admin')
def appointment_slot_availability(request):
    """JSON: which clinic time slots are free for a doctor on a given date."""
    date_value = parse_date((request.GET.get('date') or '').strip())
    if date_value is None:
        return JsonResponse({'ok': False, 'error': 'Please select a valid date.'}, status=400)

    today = timezone.localdate()
    if date_value < today:
        return JsonResponse({
            'ok': False,
            'error': 'Cannot schedule appointments for past dates.',
            'available': [],
            'occupied': [],
            'reasons': {},
        })

    if date_value.weekday() >= 5:
        return JsonResponse({
            'ok': False,
            'error': 'Appointments are not available on weekends.',
            'available': [],
            'occupied': [],
            'reasons': {},
        })

    if role_matches(request.user.role, ROLE_PATIENT):
        max_days = get_clinic_settings().max_advance_booking_days
        if date_value > today + timedelta(days=max_days):
            return JsonResponse({
                'ok': False,
                'error': f'Appointments can only be booked up to {max_days} days in advance.',
                'available': [],
                'occupied': [],
                'reasons': {},
            })

    doctor_id = (request.GET.get('doctor') or '').strip()
    doctor = None
    if doctor_id:
        doctor = User.objects.filter(id=doctor_id, is_active=True).first()
        if doctor is None or (
            doctor.role != ROLE_DOCTOR and doctor.id != request.user.id
        ):
            return JsonResponse({'ok': False, 'error': 'Invalid doctor selected.'}, status=400)
    elif role_matches(request.user.role, ROLE_DOCTOR):
        doctor = request.user
    else:
        return JsonResponse({'ok': False, 'error': 'Please select a doctor first.'}, status=400)

    patient = None
    if role_matches(request.user.role, ROLE_PATIENT):
        patient = request.user
    else:
        patient_id = (request.GET.get('patient') or '').strip()
        if patient_id:
            patient = User.objects.filter(id=patient_id, role__in=PATIENT_ROLE_VALUES).first()

    payload = classify_clinic_time_slots(doctor, date_value, patient=patient)
    return JsonResponse({
        'ok': True,
        'available': payload['available'],
        'occupied': payload['occupied'],
        'reasons': payload['reasons'],
    })
