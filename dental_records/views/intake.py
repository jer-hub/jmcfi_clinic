"""Guest and student dental intake views."""

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from appointments.models import Appointment
from core.decorators import role_required
from core.guest_auth import is_guest_user, resolve_patient_contact_email
from dental_records.forms import StudentDentalIntakeForm
from dental_records.models import (
    DentalExamination,
    DentalHistory,
    DentalHealthQuestionnaire,
    DentalRecord,
    DentalSystemsReview,
    DentalVitalSigns,
)
from .helpers import (
    _audit_dental,
    _create_guest_dental_intake_draft,
)
from medical_records.models import MedicalRecord

User = get_user_model()


@login_required
@role_required('doctor')
@require_POST
def send_guest_intake_link(request):
    """From New Dental Record: create guest draft; optionally email magic intake link."""
    from core.guest_emails import email_guest_dental_intake_pending
    from core.notification_delivery import format_email_send_error

    action = (request.POST.get('action') or 'send').strip()
    save_only = action == 'save_draft'
    patient_id = (request.POST.get('patient') or '').strip()
    appointment_id = (request.POST.get('appointment') or '').strip()

    patient = get_object_or_404(User, pk=patient_id) if patient_id else None
    if not patient or not is_guest_user(patient):
        messages.error(
            request,
            'Select a guest patient before saving a draft or sending an intake link.',
        )
        return redirect('dental_records:dental_record_create')

    appointment = None
    if appointment_id:
        appointment = get_object_or_404(Appointment, pk=appointment_id)
        if appointment.patient_id != patient.pk:
            messages.error(request, 'Guest does not match the linked appointment.')
            return redirect('dental_records:dental_record_create')
        existing = DentalRecord.objects.filter(appointment=appointment).first()
        if existing:
            messages.warning(request, 'A dental record already exists for this appointment.')
            return redirect('dental_records:dental_record_edit', record_id=existing.id)
        if MedicalRecord.objects.filter(appointment=appointment).exists():
            messages.warning(
                request,
                'A medical record already exists for this appointment. Only one record per appointment is allowed.',
            )
            return redirect('appointments:appointment_detail', appointment_id=appointment.id)

    try:
        with transaction.atomic():
            locked_appointment = None
            if appointment:
                locked_appointment = Appointment.objects.select_for_update().get(pk=appointment.pk)
                if DentalRecord.objects.filter(appointment=locked_appointment).exists():
                    existing = DentalRecord.objects.filter(appointment=locked_appointment).first()
                    messages.warning(request, 'A dental record already exists for this appointment.')
                    return redirect('dental_records:dental_record_edit', record_id=existing.id)
                if MedicalRecord.objects.filter(appointment=locked_appointment).exists():
                    messages.warning(
                        request,
                        'A medical record already exists for this appointment. Only one record per appointment is allowed.',
                    )
                    return redirect('appointments:appointment_detail', appointment_id=locked_appointment.id)

            dental_record = _create_guest_dental_intake_draft(
                patient=patient,
                examined_by=request.user,
                appointment=locked_appointment,
            )
            _audit_dental(
                request,
                dental_record,
                'create',
                intake='guest_draft' if save_only else 'guest_email',
            )
    except Exception as exc:
        messages.error(request, f'Error creating dental intake draft: {exc}')
        create_url = reverse('dental_records:dental_record_create')
        if appointment_id:
            create_url = f'{create_url}?appointment={appointment_id}'
        elif patient_id:
            create_url = f'{create_url}?patient={patient_id}'
        return redirect(create_url)

    if save_only:
        messages.success(
            request,
            'Guest dental draft saved. You can email the intake link from the record page when ready.',
        )
        return redirect('dental_records:dental_record_detail', record_id=dental_record.id)

    contact = resolve_patient_contact_email(patient)
    emailed = False
    email_error = ''
    try:
        emailed = email_guest_dental_intake_pending(
            request, dental_record, created_by=request.user
        )
    except Exception as email_exc:
        email_error = format_email_send_error(email_exc)
        emailed = False

    if not contact:
        messages.warning(
            request,
            'Draft created, but this guest has no contact email — they were not emailed.',
        )
    elif emailed:
        messages.success(request, f'Dental intake link emailed to {contact}.')
    else:
        detail = email_error or 'check clinic email settings / EMAIL_BACKEND'
        messages.warning(
            request,
            f'Draft created, but the email was not sent ({detail}).',
        )

    return redirect('dental_records:dental_record_detail', record_id=dental_record.id)


@login_required
@role_required('doctor', 'admin')
@require_POST
def resend_guest_intake_link(request, record_id):
    """Re-issue magic link while dental intake is still awaiting the guest."""
    from core.guest_emails import email_guest_dental_intake_pending
    from core.notification_delivery import format_email_send_error

    dental_record = get_object_or_404(
        DentalRecord.objects.select_related('patient', 'patient__patient_profile'),
        pk=record_id,
    )
    if not is_guest_user(dental_record.patient):
        messages.error(request, 'Resend link is only available for guest patients.')
        return redirect('dental_records:dental_record_detail', record_id=record_id)
    if dental_record.intake_status != 'awaiting_guest':
        messages.error(request, 'Resend link is only available while awaiting guest intake.')
        return redirect('dental_records:dental_record_detail', record_id=record_id)

    contact = resolve_patient_contact_email(dental_record.patient)
    emailed = False
    email_error = ''
    try:
        emailed = email_guest_dental_intake_pending(
            request, dental_record, created_by=request.user
        )
    except Exception as email_exc:
        email_error = format_email_send_error(email_exc)
        emailed = False

    if not contact:
        messages.warning(request, 'This guest has no contact email — link was not sent.')
    elif emailed:
        messages.success(request, f'Dental intake link resent to {contact}.')
    else:
        detail = email_error or 'check clinic email settings / EMAIL_BACKEND'
        messages.warning(request, f'Could not resend the email ({detail}).')

    next_url = (request.POST.get('next') or '').strip()
    if next_url.startswith('/'):
        return redirect(next_url)
    return redirect('dental_records:dental_record_detail', record_id=record_id)


@login_required
def student_dental_intake(request, appointment_id):
    """
    Allow a student to fill in their own dental intake form (demographics +
    consent) after their dental appointment has been confirmed by a doctor.

    Guards:
    - Appointment must belong to the logged-in user.
    - Appointment type must be 'dental'.
    - Appointment status must be 'confirmed'.
    - No dental record may already exist for this appointment.
    """
    appointment = get_object_or_404(
        Appointment,
        pk=appointment_id,
        patient=request.user,
        appointment_type='dental',
    )

    # Appointment must be confirmed before student can fill the form
    if appointment.status != 'confirmed':
        if appointment.status == 'pending':
            messages.warning(
                request,
                'Your appointment has not been confirmed yet. '
                'You will be able to fill in your dental form once the doctor confirms it.'
            )
        elif appointment.status == 'completed':
            # Check if a dental record already exists
            existing = DentalRecord.objects.filter(appointment=appointment).first()
            if existing:
                messages.info(request, 'Your dental intake has already been submitted.')
                return redirect('dental_records:dental_record_list')
            messages.warning(request, 'This appointment is already completed.')
        else:
            messages.warning(request, 'This appointment is not available for intake.')
        return redirect('appointments:appointment_detail', appointment_id=appointment_id)

    # Check if a dental record already exists for this appointment
    existing_record = DentalRecord.objects.filter(appointment=appointment).first()
    if existing_record:
        messages.info(
            request,
            'You have already submitted your dental intake form for this appointment. '
            'The doctor will complete your record during your visit.'
        )
        return redirect('dental_records:dental_record_list')

    if request.method == 'POST':
        form = StudentDentalIntakeForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    # Re-verify inside the transaction to prevent race conditions
                    locked_appointment = Appointment.objects.select_for_update().get(
                        pk=appointment.pk,
                        patient=request.user,
                        status='confirmed',
                    )
                    if DentalRecord.objects.filter(appointment=locked_appointment).exists():
                        messages.warning(
                            request,
                            'Your dental intake form has already been submitted.'
                        )
                        return redirect('dental_records:dental_record_list')

                    dental_record = form.save(commit=False)
                    dental_record.patient = request.user
                    dental_record.appointment = locked_appointment
                    dental_record.examined_by = locked_appointment.doctor
                    dental_record.date_of_examination = timezone.now().date()
                    dental_record.status = 'pending'
                    dental_record.save()

                    # Create placeholder records so the doctor's edit page
                    # has all sections ready to fill in.
                    DentalExamination.objects.create(dental_record=dental_record)
                    DentalVitalSigns.objects.create(dental_record=dental_record)
                    DentalHealthQuestionnaire.objects.create(dental_record=dental_record)
                    DentalSystemsReview.objects.create(dental_record=dental_record)
                    DentalHistory.objects.create(dental_record=dental_record)

                _audit_dental(request, dental_record, 'create')

                messages.success(
                    request,
                    'Your dental intake form has been submitted successfully! '
                    'Your assigned doctor will complete the examination during your appointment.'
                )
                return redirect('dental_records:dental_record_list')
            except Exception as e:
                messages.error(request, f'An error occurred while saving your form: {str(e)}')
        else:
            messages.error(request, 'Please correct the errors highlighted below.')
    else:
        # Pre-fill from the student\'s profile
        initial_data = {
            'email': request.user.email,
            'designation': 'student',
        }
        try:
            if hasattr(request.user, 'patient_profile') and request.user.patient_profile:
                profile = request.user.patient_profile
                is_employee = bool(getattr(profile, 'is_employee', False))
                from datetime import date
                initial_data.update({
                    'middle_name': profile.middle_name or '',
                    'age': profile.age or '',
                    'gender': profile.gender or '',
                    'civil_status': profile.civil_status or 'single',
                    'address': profile.address or '',
                    'date_of_birth': profile.date_of_birth,
                    'place_of_birth': profile.place_of_birth or '',
                    'contact_number': profile.phone or '',
                    'telephone_number': getattr(profile, 'telephone_number', '') or '',
                    'designation': 'employee' if is_employee else 'student',
                    'department_college_office': (
                        (profile.department or '')
                        if is_employee
                        else f"{profile.course or ''} - {profile.department or ''}".strip(' -')
                    ),
                    'guardian_name': profile.emergency_contact or '',
                    'guardian_contact': profile.emergency_phone or '',
                })
                if profile.date_of_birth and not initial_data.get('age'):
                    today = date.today()
                    dob = profile.date_of_birth
                    initial_data['age'] = (
                        today.year - dob.year
                        - ((today.month, today.day) < (dob.month, dob.day))
                    )
        except Exception:
            pass
        form = StudentDentalIntakeForm(initial=initial_data)

    context = {
        'form': form,
        'appointment': appointment,
        'title': 'Dental Intake Form',
    }
    return render(request, 'dental_records/student_dental_intake.html', context)
