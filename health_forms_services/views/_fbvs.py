"""Function-based views that remain after the CBV migration.

All list/detail/edit pages are now class-based (see ``forms_cbvs.py`` and
``_cbvs.py``). The functions here cover the create/review/delete/export and
HTMX/JSON API surface that the URL config still wires up.
"""

import json

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from core.decorators import role_required
from core.roles import PATIENT_ROLE_VALUES
from core.guest_auth import create_guest_user, get_or_create_guest_for_invite, is_guest_user
from core.academic_catalog import patient_catalog_context

from ..exports import (
    doc_to_response,
    generate_dental_form,
    generate_dental_services,
    generate_health_profile,
    generate_patient_chart,
)
from ..forms import (
    DentalHealthConditionsForm,
    DentalHealthExaminationForm,
    DentalHealthFormReviewForm,
    DentalHealthPersonalInfoForm,
    DentalServicesPersonalInfoForm,
    DentalServicesReviewForm,
    GuestHealthFormInviteForm,
    HealthFormReviewForm,
    HealthProfileClinicalSummaryForm,
    HealthProfileDiagnosticTestsForm,
    HealthProfileMedicalHistoryForm,
    HealthProfilePersonalInfoForm,
    HealthProfilePhysicalExamForm,
    PatientChartEntryForm,
    PatientChartPersonalInfoForm,
    PatientChartReviewForm,
    PrescriptionItemForm,
    PrescriptionPatientForm,
    PrescriptionReviewForm,
)
from ..picker_mappings import clinical_module_for_form_key, picker_field_mappings
from ..models import (
    DentalFormTooth,
    DentalFormToothSurface,
    DentalHealthForm,
    DentalServicesRequest,
    HealthProfileForm,
    PatientChart,
    PatientChartEntry,
    Prescription,
    PrescriptionItem,
)

User = get_user_model()


# ── Helpers ────────────────────────────────────────────────────────────────


def _is_json_request(request):
    content_type = (request.content_type or '').lower()
    return content_type.startswith('application/json')


def _selected_patient_from_request(request):
    """Resolve selected patient from explicit picker input for doctor/staff create flows."""
    raw_patient_id = (request.POST.get('selected_user_id') or '').strip()
    if not raw_patient_id:
        return None, None
    try:
        patient_id = int(raw_patient_id)
    except (TypeError, ValueError):
        return None, 'Please select a valid patient from the search results.'
    patient = User.objects.filter(pk=patient_id, role__in=PATIENT_ROLE_VALUES).first()
    if not patient:
        return None, 'Please select a valid patient from the search results.'
    return patient, None


def _phone_from_personal_cleaned(cleaned_data):
    for key in ('mobile_number', 'contact_number', 'telephone_number'):
        value = (cleaned_data.get(key) or '').strip()
        if value:
            return value
    return None


def _names_from_personal_cleaned(cleaned_data):
    first = (cleaned_data.get('first_name') or '').strip()
    last = (cleaned_data.get('last_name') or '').strip()
    if first and last:
        return first, last
    patient_name = (cleaned_data.get('patient_name') or '').strip()
    if not patient_name:
        return '', ''
    parts = patient_name.split(None, 1)
    if len(parts) == 2:
        return parts[0], parts[1]
    return parts[0], 'Guest'


def _resolve_create_patient(request, personal_form):
    """
    Patient for staff create flows: picker selection, or guest from profiling fields on submit.
    """
    patient, picker_error = _selected_patient_from_request(request)
    if picker_error:
        return None, picker_error
    if patient:
        return patient, None

    registering_guest = request.POST.get('register_guest') == '1'
    if not registering_guest:
        return None, 'Please search for a patient or check Register guest patient.'

    if not personal_form.is_valid():
        return None, None

    first_name, last_name = _names_from_personal_cleaned(personal_form.cleaned_data)
    if not first_name or not last_name:
        return None, 'First and last name are required for guest registration.'

    phone = _phone_from_personal_cleaned(personal_form.cleaned_data)
    gender = personal_form.cleaned_data.get('gender') or None
    date_of_birth = personal_form.cleaned_data.get('date_of_birth')
    contact_email = (
        (personal_form.cleaned_data.get('email_address') or '').strip()
        or None
    )
    if not contact_email:
        return None, 'A contact email is required for guest registration.'

    return create_guest_user(
        first_name=first_name,
        last_name=last_name,
        phone=phone,
        gender=gender,
        date_of_birth=date_of_birth,
        contact_email=contact_email,
    ), None


def _patient_search_result_payload(patient):
    """Shared payload contract for patient picker search results."""
    profile = getattr(patient, 'patient_profile', None)
    patient_id = getattr(profile, 'patient_id', '') or ''
    course = getattr(profile, 'course', '') or ''
    year_level = getattr(profile, 'year_level', '') or ''
    detail_bits = [bit for bit in (course, year_level) if bit]
    detail = ' · '.join(detail_bits) if detail_bits else 'Patient'
    return {
        'id': patient.id,
        'name': patient.get_full_name() or patient.email or f'User {patient.id}',
        'email': patient.email or '',
        'patient_id': patient_id,
        'detail': detail,
        'display': f"{patient.get_full_name() or patient.email} ({patient_id or patient.email})",
    }


def _patient_profile_prefill_payload(patient):
    """Shared payload contract for auto-prefilling create transaction forms."""
    profile = getattr(patient, 'patient_profile', None)
    staff_profile = getattr(patient, 'staff_profile', None)
    is_employee = bool(getattr(profile, 'is_employee', False)) if profile else False
    is_guest = is_guest_user(patient)
    if is_guest:
        default_designation = 'guest'
        is_employee = False
    elif staff_profile and not profile:
        default_designation = 'employee'
        is_employee = True
    elif is_employee:
        default_designation = 'employee'
    else:
        default_designation = 'student'

    department = getattr(profile, 'department', '') or ''
    course = '' if (is_employee or is_guest) else (getattr(profile, 'course', '') or '')
    year_level = '' if (is_employee or is_guest) else (getattr(profile, 'year_level', '') or '')
    if is_guest:
        department_college_office = ''
    elif is_employee:
        department_college_office = department
    else:
        department_college_office = department

    return {
        'id': patient.id,
        'name': patient.get_full_name() or patient.email or '',
        'first_name': patient.first_name or '',
        'last_name': patient.last_name or '',
        'middle_name': getattr(profile, 'middle_name', '') or '',
        'email_address': patient.email or '',
        'gender': getattr(profile, 'gender', '') or '',
        'civil_status': getattr(profile, 'civil_status', '') or '',
        'religion': getattr(profile, 'religion', '') or '',
        'citizenship': getattr(profile, 'citizenship', '') or '',
        'date_of_birth': (
            profile.date_of_birth.isoformat()
            if profile and getattr(profile, 'date_of_birth', None)
            else ''
        ),
        'place_of_birth': getattr(profile, 'place_of_birth', '') or '',
        'age': getattr(profile, 'age', '') or '',
        'address': getattr(profile, 'address', '') or '',
        'contact_number': getattr(profile, 'phone', '') or '',
        'telephone_number': getattr(profile, 'telephone_number', '') or '',
        'designation': default_designation,
        'department_college_office': department_college_office,
        'department': department_college_office,
        'guardian_name': getattr(profile, 'emergency_contact', '') or '',
        'guardian_contact': getattr(profile, 'emergency_phone', '') or '',
        'patient_id': getattr(profile, 'patient_id', '') or '',
        'permanent_address': getattr(profile, 'address', '') or '',
        'zip_code': getattr(profile, 'zip_code', '') or '',
        'current_address': getattr(profile, 'address', '') or '',
        'mobile_number': getattr(profile, 'phone', '') or '',
        'course': course,
        'year_level': year_level,
        'institution_id': getattr(profile, 'patient_id', '') or '',
        'blood_type': getattr(profile, 'blood_type', '') or '',
        'allergies': getattr(profile, 'allergies', '') or '',
        'medical_conditions': getattr(profile, 'medical_conditions', '') or '',
    }


def _patient_picker_config(request, form_key, selected_patient=None):
    """Serializable Alpine config for the shared patient picker (safe for json_script)."""
    initial_selected = None
    if selected_patient:
        payload = _patient_search_result_payload(selected_patient)
        initial_selected = {
            'id': str(payload['id']),
            'name': payload['name'],
            'email': payload['email'],
            'patientId': payload['patient_id'],
        }
    return {
        'searchUrl': reverse('health_forms_services:search_patients'),
        'profileUrlTemplate': reverse(
            'health_forms_services:patient_profile_prefill',
            args=[0],
        ),
        'initialSelected': initial_selected,
        'fieldMappings': picker_field_mappings(form_key),
        'registerGuestUrl': reverse('core:register_guest_patient'),
        'clinicalModule': clinical_module_for_form_key(form_key),
    }


def _patient_picker_create_context(request, form_key, selected_patient=None):
    """Shared template context for patient picker on create flows."""
    return {
        'selected_patient': selected_patient,
        'selected_patient_payload': (
            _patient_search_result_payload(selected_patient) if selected_patient else None
        ),
        'hf_picker_config': _patient_picker_config(request, form_key, selected_patient),
        'clinical_module': clinical_module_for_form_key(form_key),
        **patient_catalog_context(),
    }


def _preselected_patient_from_request(request):
    """Optional ?patient= / ?patient_id= query pre-selection for create forms."""
    raw_patient_id = (request.GET.get('patient') or request.GET.get('patient_id') or '').strip()
    if not raw_patient_id:
        return None
    try:
        return User.objects.select_related('patient_profile').get(
            pk=int(raw_patient_id),
            role__in=PATIENT_ROLE_VALUES,
        )
    except (User.DoesNotExist, TypeError, ValueError):
        return None


def get_form_or_404(model, pk, user, select_related_fields=None):
    """Get a form object honouring role-based access control."""
    queryset = model.objects.all()
    if select_related_fields:
        queryset = queryset.select_related(*select_related_fields)
    from core.roles import is_patient_role
    if is_patient_role(user.role):
        queryset = queryset.filter(user=user)
    return get_object_or_404(queryset, pk=pk)


# ═══════════════════════════════════════════════════════════════════════════
# Health Profile Form (F-HSS-20-0001) — create, section load, review, delete,
# export
# ═══════════════════════════════════════════════════════════════════════════


@login_required
@role_required('staff', 'doctor')
def manual_entry(request):
    """Create a new health profile form using personal info only."""
    selected_patient = None
    if request.method == 'POST':
        personal_form = HealthProfilePersonalInfoForm(request.POST)
        selected_patient, selected_patient_error = _resolve_create_patient(request, personal_form)
        if selected_patient_error:
            personal_form.add_error(None, selected_patient_error)
        if personal_form.is_valid() and not selected_patient_error and selected_patient:
            health_form = HealthProfileForm(user=selected_patient)
            for field in personal_form.cleaned_data:
                setattr(health_form, field, personal_form.cleaned_data[field])
            # Start as draft so the patient can finish history online, or staff can submit in-clinic.
            health_form.status = HealthProfileForm.Status.INCOMPLETE
            health_form.save()

            from core.guest_emails import (
                email_guest_health_form_pending,
                email_patient_health_form_pending,
            )
            from core.notification_delivery import format_email_send_error, notify_user
            from core.guest_auth import is_guest_user, resolve_patient_contact_email

            # Keep contact email on existing guests in sync with the form snapshot.
            form_email = (personal_form.cleaned_data.get('email_address') or '').strip()
            if is_guest_user(selected_patient) and form_email:
                profile = getattr(selected_patient, 'patient_profile', None)
                if profile and profile.contact_email != form_email:
                    profile.contact_email = form_email
                    profile.save(update_fields=['contact_email'])

            emailed = False
            email_error = ''
            contact = resolve_patient_contact_email(selected_patient)

            if is_guest_user(selected_patient):
                try:
                    emailed = email_guest_health_form_pending(
                        request, health_form, created_by=request.user
                    )
                except Exception as email_exc:
                    email_error = format_email_send_error(email_exc)
                    emailed = False
            else:
                notify_user(
                    selected_patient,
                    title='Complete your health profile',
                    message=(
                        'The clinic started a health profile form for you. '
                        'Please finish your demographics and medical history, then submit for review.'
                    ),
                    notification_type='general',
                    transaction_type='health_form_incomplete',
                    related_id=health_form.pk,
                    send_email=False,
                )
                try:
                    emailed = email_patient_health_form_pending(request, health_form)
                except Exception as email_exc:
                    email_error = format_email_send_error(email_exc)
                    emailed = False

            if not contact:
                messages.warning(
                    request,
                    'Draft created, but this patient has no contact email — they were not emailed.',
                )
            elif emailed:
                messages.success(request, f'Health-form link emailed to {contact}.')
            else:
                detail = email_error or 'check clinic email settings / EMAIL_BACKEND'
                messages.warning(
                    request,
                    f'Draft created, but the email was not sent ({detail}).',
                )

            messages.success(
                request,
                'Health profile form created as a draft. Complete personal/history, then submit for review.',
            )
            return redirect('health_forms_services:edit_form', pk=health_form.pk)
    else:
        preselected = _preselected_patient_from_request(request)
        selected_patient = preselected
        initial = _patient_profile_prefill_payload(preselected) if preselected else None
        personal_form = HealthProfilePersonalInfoForm(initial=initial)

    return render(request, 'health_forms_services/manual_entry.html', {
        'personal_form': personal_form,
        **_patient_picker_create_context(request, 'health_profile', selected_patient),
    })


@login_required
@role_required('staff', 'doctor')
def invite_guest_health_profile(request):
    """Invite a guest by name + contact email to complete a health profile online."""
    if request.method == 'POST':
        form = GuestHealthFormInviteForm(request.POST)
        if form.is_valid():
            first_name = form.cleaned_data['first_name'].strip()
            last_name = form.cleaned_data['last_name'].strip()
            contact_email = form.cleaned_data['contact_email']
            mobile = (form.cleaned_data.get('mobile_number') or '').strip() or None

            guest, _created = get_or_create_guest_for_invite(
                first_name=first_name,
                last_name=last_name,
                contact_email=contact_email,
                phone=mobile,
            )

            health_form = HealthProfileForm(
                user=guest,
                status=HealthProfileForm.Status.INCOMPLETE,
                designation=HealthProfileForm.Designation.GUEST,
                first_name=first_name,
                last_name=last_name,
                email_address=contact_email,
                mobile_number=mobile or '',
            )
            health_form.save()

            from core.guest_emails import email_guest_health_form_pending
            from core.guest_auth import resolve_patient_contact_email
            from core.notification_delivery import format_email_send_error

            emailed = False
            email_error = ''
            contact = resolve_patient_contact_email(guest)
            try:
                emailed = email_guest_health_form_pending(
                    request, health_form, created_by=request.user
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
                messages.success(request, f'Health-form link emailed to {contact}.')
            else:
                detail = email_error or 'check clinic email settings / EMAIL_BACKEND'
                messages.warning(
                    request,
                    f'Draft created, but the email was not sent ({detail}).',
                )

            messages.success(
                request,
                'Guest health profile draft created. They can complete personal and medical history online.',
            )
            return redirect('health_forms_services:form_detail', pk=health_form.pk)
    else:
        form = GuestHealthFormInviteForm()

    return render(request, 'health_forms_services/invite_guest.html', {
        'form': form,
    })


@login_required
@role_required('staff', 'doctor')
@require_POST
def resend_guest_health_form_link(request, pk):
    """Re-issue magic link email for an incomplete guest health profile draft."""
    health_form = get_form_or_404(
        HealthProfileForm, pk, request.user, select_related_fields=['user', 'user__patient_profile']
    )
    if not is_guest_user(health_form.user):
        messages.error(request, 'Resend link is only available for guest patients.')
        return redirect('health_forms_services:form_detail', pk=pk)
    if health_form.status != HealthProfileForm.Status.INCOMPLETE:
        messages.error(request, 'Resend link is only available while the form is still a draft.')
        return redirect('health_forms_services:form_detail', pk=pk)

    from core.guest_emails import email_guest_health_form_pending
    from core.guest_auth import resolve_patient_contact_email
    from core.notification_delivery import format_email_send_error

    contact = resolve_patient_contact_email(health_form.user)
    emailed = False
    email_error = ''
    try:
        emailed = email_guest_health_form_pending(
            request, health_form, created_by=request.user
        )
    except Exception as email_exc:
        email_error = format_email_send_error(email_exc)
        emailed = False

    if not contact:
        messages.warning(request, 'This guest has no contact email — link was not sent.')
    elif emailed:
        messages.success(request, f'Health-form link resent to {contact}.')
    else:
        detail = email_error or 'check clinic email settings / EMAIL_BACKEND'
        messages.warning(request, f'Could not resend the email ({detail}).')

    next_url = (request.POST.get('next') or '').strip()
    if next_url.startswith('/'):
        return redirect(next_url)
    return redirect('health_forms_services:form_detail', pk=pk)


@login_required
@role_required('patient')
def request_health_profile(request):
    """Patient creates (or resumes) an incomplete health profile draft with profile prefill."""
    existing = (
        HealthProfileForm.objects
        .filter(user=request.user, status=HealthProfileForm.Status.INCOMPLETE)
        .order_by('-updated_at')
        .first()
    )
    if existing:
        messages.info(request, 'You already have a draft form. Continue editing it.')
        return redirect('health_forms_services:edit_form', pk=existing.pk)

    from health_forms_services.services import apply_health_profile_prefill

    health_form = HealthProfileForm(
        user=request.user,
        status=HealthProfileForm.Status.INCOMPLETE,
    )
    # Reload so OneToOne profile is available for prefill after signal-created rows.
    patient = User.objects.select_related('patient_profile').get(pk=request.user.pk)
    apply_health_profile_prefill(health_form, _patient_profile_prefill_payload(patient))
    health_form.save()
    messages.success(request, 'Health profile form started. Complete your information, then submit for review.')
    return redirect('health_forms_services:edit_form', pk=health_form.pk)


@login_required
@require_POST
def submit_for_review(request, pk):
    """Submit an incomplete draft for clinic review (patient owner or assisting clinician)."""
    from health_forms_services.services import (
        can_submit_for_review,
        visible_edit_tabs,
        validate_submit_for_review,
    )

    health_form = get_form_or_404(
        HealthProfileForm, pk, request.user,
        ['user', 'reviewed_by', 'examining_physician'],
    )
    if not can_submit_for_review(request.user, health_form):
        messages.error(request, 'You cannot submit this form for review.')
        return redirect('health_forms_services:form_detail', pk=pk)

    errors = validate_submit_for_review(health_form)
    if errors:
        from health_forms_services.services import (
            GUEST_SUBMIT_REQUIRED_FIELDS,
            SUBMIT_REQUIRED_FIELDS,
        )
        from .forms_cbvs import HealthProfileEditView

        designation = (getattr(health_form, 'designation', None) or '').strip().lower()
        guest_form = designation == 'guest' or is_guest_user(getattr(health_form, 'user', None))
        required_fields = GUEST_SUBMIT_REQUIRED_FIELDS if guest_form else SUBMIT_REQUIRED_FIELDS

        form_view = HealthProfileEditView()
        form_view.request = request
        form_view.kwargs = {'pk': pk}

        tabs = visible_edit_tabs(request.user, health_form, form_view.tabs)
        form_instances = {}
        for key, form_class in form_view.form_class_map.items():
            if key not in {t['key'] for t in tabs}:
                continue
            form_instances[key] = form_view._build_form(
                form_class,
                instance=health_form,
                section=key,
            )

        personal_form = form_instances.get('personal')
        if personal_form is not None:
            posted = {}
            for field_name, field in personal_form.fields.items():
                value = getattr(health_form, field_name, '')
                if field_name == 'is_employee':
                    posted[field_name] = 'on' if (getattr(health_form, 'designation', '') or '').strip().lower() in {'staff', 'employee'} else ''
                    continue
                if hasattr(value, 'isoformat'):
                    posted[field_name] = value.isoformat() if value else ''
                else:
                    posted[field_name] = '' if value is None else str(value)
            posted['section'] = 'personal'
            personal_form = form_view._build_form(
                form_view.form_class_map['personal'],
                instance=health_form,
                data=posted,
                section='personal',
            )
            personal_form.is_valid()

            for field_name in required_fields:
                value = getattr(health_form, field_name, None)
                if value is None or (isinstance(value, str) and not value.strip()):
                    if field_name not in personal_form.errors:
                        label = personal_form.fields.get(field_name).label if field_name in personal_form.fields else field_name.replace('_', ' ').title()
                        personal_form.add_error(field_name, f'{label} is required before submitting for review.')
            form_instances['personal'] = personal_form

        ctx = form_view.get_edit_context(
            health_form,
            active_section='personal',
            form_instances=form_instances,
        )
        ctx.update(form_view.get_extra_edit_context(health_form))
        return render(request, form_view.template_name, ctx)

    health_form.status = HealthProfileForm.Status.PENDING
    health_form.save(update_fields=['status', 'updated_at'])
    from health_forms_services.services import notify_clinicians_health_form_submitted

    notify_clinicians_health_form_submitted(health_form, actor=request.user)
    messages.success(request, 'Form submitted for clinic review.')
    return redirect('health_forms_services:form_detail', pk=pk)


@login_required
@require_POST
def cancel_draft(request, pk):
    """Cancel an incomplete draft or pending submission (patient owner or clinician)."""
    from health_forms_services.services import can_cancel_draft

    health_form = get_form_or_404(
        HealthProfileForm, pk, request.user,
        ['user', 'reviewed_by', 'examining_physician'],
    )
    if not can_cancel_draft(request.user, health_form):
        messages.error(request, 'You cannot cancel this form.')
        return redirect('health_forms_services:form_detail', pk=pk)

    was_pending = health_form.status == HealthProfileForm.Status.PENDING
    health_form.status = HealthProfileForm.Status.CANCELLED
    health_form.save(update_fields=['status', 'updated_at'])
    if was_pending:
        messages.success(request, 'Health form submission cancelled.')
    else:
        messages.success(request, 'Health form draft cancelled.')
    return redirect('health_forms_services:forms_list')


@login_required
@role_required('staff', 'doctor', 'patient')
def load_form_section(request, pk):
    """Return a section's serialized fields for lazy-loaded edit tabs."""
    from health_forms_services.services import editable_sections

    section = request.GET.get('section', 'personal')
    health_form = get_form_or_404(HealthProfileForm, pk, request.user,
                                  ['user', 'reviewed_by', 'examining_physician'])

    if section not in editable_sections(request.user, health_form):
        return JsonResponse({'error': 'You cannot load this section for editing.'}, status=403)

    form_map = {
        'personal': HealthProfilePersonalInfoForm,
        'medical': HealthProfileMedicalHistoryForm,
        'physical': HealthProfilePhysicalExamForm,
        'diagnostic': HealthProfileDiagnosticTestsForm,
        'clinical': HealthProfileClinicalSummaryForm,
    }
    form = form_map.get(section, HealthProfilePersonalInfoForm)(instance=health_form)

    form_fields = {}
    for name, field in form.fields.items():
        value = form.initial.get(name, '')
        form_fields[name] = {
            'value': str(value) if value else '',
            'label': field.label or name,
            'required': field.required,
            'widget_type': type(field.widget).__name__,
        }

    return JsonResponse({'section': section, 'fields': form_fields})


@login_required
@require_POST
def review_form(request, pk):
    if request.user.role not in ['staff', 'doctor', 'admin']:
        messages.error(request, 'Permission denied.')
        return redirect('health_forms_services:form_detail', pk=pk)

    health_form = get_object_or_404(HealthProfileForm, pk=pk)
    form = HealthFormReviewForm(request.POST, instance=health_form)
    if form.is_valid():
        health_form = form.save(commit=False)
        health_form.reviewed_by = request.user
        health_form.reviewed_at = timezone.now()
        # Reject returns the form to incomplete so the patient can revise and resubmit.
        if health_form.status == HealthProfileForm.Status.REJECTED:
            health_form.status = HealthProfileForm.Status.INCOMPLETE
            health_form.save()
            messages.success(
                request,
                'Form rejected and returned to the patient for revision.',
            )
        else:
            health_form.save()
            if health_form.status == HealthProfileForm.Status.COMPLETED:
                from health_forms_services.services import notify_patient_health_form_completed

                notify_patient_health_form_completed(health_form)
            messages.success(request, f'Form status updated to {health_form.get_status_display()}.')
    else:
        messages.error(request, 'Invalid form data.')
    return redirect('health_forms_services:form_detail', pk=pk)


@login_required
@require_POST
def delete_form(request, pk):
    from health_forms_services.services import can_delete_health_profile

    health_form = get_form_or_404(
        HealthProfileForm, pk, request.user,
        ['user', 'reviewed_by', 'examining_physician'],
    )
    if not can_delete_health_profile(request.user, health_form):
        messages.error(request, 'You cannot delete this form.')
        return redirect('health_forms_services:form_detail', pk=pk)

    health_form.delete()
    messages.success(request, 'Form deleted successfully.')
    return redirect('health_forms_services:forms_list')


@login_required
@require_GET
@role_required('staff', 'doctor')
def export_form_json(request, pk):
    user = request.user
    if user.role in ['staff', 'doctor', 'admin']:
        health_form = get_object_or_404(HealthProfileForm, pk=pk)
    else:
        health_form = get_object_or_404(HealthProfileForm, pk=pk, user=user)

    designation_value = (health_form.designation or '').strip().lower()
    department_value = (
        ''
        if designation_value == 'guest'
        else health_form.department_college_office
    )

    data = {
        'personal_info': {
            'name': health_form.get_full_name(),
            'last_name': health_form.last_name,
            'first_name': health_form.first_name,
            'middle_name': health_form.middle_name,
            'date_of_birth': str(health_form.date_of_birth) if health_form.date_of_birth else None,
            'age': health_form.age,
            'gender': health_form.gender,
            'civil_status': health_form.civil_status,
            'citizenship': health_form.citizenship,
            'religion': health_form.religion,
            'permanent_address': health_form.permanent_address,
            'current_address': health_form.current_address,
            'zip_code': health_form.zip_code,
            'email': health_form.email_address,
            'mobile': health_form.mobile_number,
            'telephone': health_form.telephone_number,
            'designation': health_form.designation,
            'department': department_value,
            'emergency_contact': {
                'name': health_form.guardian_name,
                'contact': health_form.guardian_contact,
            },
        },
        'medical_history': {
            'immunizations': health_form.immunization_records,
            'illness_history': health_form.illness_history,
            'allergies': health_form.allergies,
            'current_medications': health_form.current_medications,
        },
        'obgyn_history': {
            'menarche_age': health_form.menarche_age,
            'menstrual_duration': health_form.menstrual_duration,
            'menstrual_interval': health_form.menstrual_interval,
            'menstrual_amount': health_form.menstrual_amount,
            'menstrual_symptoms': health_form.menstrual_symptoms,
            'obstetric_history': health_form.obstetric_history,
        },
        'present_illness': health_form.present_illness,
        'physical_examination': {
            'vital_signs': {
                'blood_pressure': health_form.blood_pressure,
                'heart_rate': health_form.heart_rate,
                'respiratory_rate': health_form.respiratory_rate,
                'temperature': float(health_form.temperature) if health_form.temperature else None,
                'spo2': float(health_form.spo2) if health_form.spo2 else None,
            },
            'anthropometrics': {
                'height': float(health_form.height) if health_form.height else None,
                'weight': float(health_form.weight) if health_form.weight else None,
                'bmi': float(health_form.bmi) if health_form.bmi else None,
                'bmi_remarks': health_form.bmi_remarks,
            },
            'findings': health_form.physical_exam_findings,
            'other_findings': health_form.other_findings,
        },
        'diagnostic_tests': health_form.diagnostic_tests,
        'clinical_summary': {
            'impression': health_form.physician_impression,
            'remarks': health_form.final_remarks,
            'recommendations': health_form.recommendations,
            'physician': health_form.examining_physician,
            'date': str(health_form.examination_date) if health_form.examination_date else None,
        },
        'metadata': {
            'status': health_form.status,
            'created_at': health_form.created_at.isoformat(),
            'updated_at': health_form.updated_at.isoformat(),
        },
    }
    return JsonResponse(data, json_dumps_params={'indent': 2})


# ═══════════════════════════════════════════════════════════════════════════
# Dental Health Forms (Dental Form 2) — create, review, delete
# ═══════════════════════════════════════════════════════════════════════════


@login_required
@role_required('staff', 'doctor')
def create_dental_form(request):
    selected_patient = None
    if request.method == 'POST':
        personal_form = DentalServicesPersonalInfoForm(request.POST)
        selected_patient, selected_patient_error = _resolve_create_patient(request, personal_form)
        if selected_patient_error:
            personal_form.add_error(None, selected_patient_error)
        if personal_form.is_valid() and not selected_patient_error and selected_patient:
            service_form = DentalServicesRequest(user=selected_patient)
            for field in personal_form.cleaned_data:
                setattr(service_form, field, personal_form.cleaned_data[field])
            service_form.status = DentalServicesRequest.Status.PENDING
            service_form.save()
            messages.success(request, 'Dental health form created. You can now fill in the services checklist.')
            return redirect(
                reverse('health_forms_services:edit_dental_form', kwargs={'pk': service_form.pk})
                + '?section=perio'
            )
    else:
        preselected = _preselected_patient_from_request(request)
        selected_patient = preselected
        initial = _patient_profile_prefill_payload(preselected) if preselected else None
        personal_form = DentalServicesPersonalInfoForm(initial=initial)

    return render(request, 'health_forms_services/create_dental_form.html', {
        'personal_form': personal_form,
        **_patient_picker_create_context(request, 'dental_form', selected_patient),
    })


@login_required
@require_POST
def review_dental_form(request, pk):
    if request.user.role not in ['staff', 'doctor', 'admin']:
        messages.error(request, 'Permission denied.')
        return redirect('health_forms_services:dental_form_detail', pk=pk)

    service_form = get_object_or_404(DentalServicesRequest, pk=pk)
    form = DentalServicesReviewForm(request.POST, instance=service_form)
    if form.is_valid():
        service_form = form.save(commit=False)
        service_form.reviewed_by = request.user
        service_form.reviewed_at = timezone.now()
        service_form.save()
        messages.success(request, f'Form status updated to {service_form.get_status_display()}.')
    else:
        messages.error(request, 'Invalid form data.')
    return redirect('health_forms_services:dental_form_detail', pk=pk)


@login_required
@role_required('staff', 'doctor')
def delete_dental_form(request, pk):
    user = request.user
    if user.role in ['staff', 'doctor', 'admin']:
        service_form = get_object_or_404(DentalServicesRequest, pk=pk)
    else:
        service_form = get_object_or_404(DentalServicesRequest, pk=pk, user=user)

    if service_form.status not in ['pending', 'rejected', 'incomplete']:
        messages.error(request, 'Cannot delete a form that has been processed.')
        return redirect('health_forms_services:dental_form_detail', pk=pk)

    service_form.delete()
    messages.success(request, 'Dental health form deleted successfully.')
    return redirect('health_forms_services:dental_forms_list')


# ═══════════════════════════════════════════════════════════════════════════
# Dental Services (HSS-Form0003) — create, review, delete, chart API
# ═══════════════════════════════════════════════════════════════════════════


@login_required
@role_required('staff', 'doctor')
def create_dental_services(request):
    selected_patient = None
    if request.method == 'POST':
        personal_form = DentalHealthPersonalInfoForm(request.POST)
        selected_patient, selected_patient_error = _resolve_create_patient(request, personal_form)
        if selected_patient_error:
            personal_form.add_error(None, selected_patient_error)
        if personal_form.is_valid() and not selected_patient_error and selected_patient:
            dental_form = DentalHealthForm(user=selected_patient)
            for field in personal_form.cleaned_data:
                setattr(dental_form, field, personal_form.cleaned_data[field])
            dental_form.status = DentalHealthForm.Status.PENDING
            dental_form.examined_by = request.user
            dental_form.save()
            messages.success(request, 'Dental services form created. You can now fill in clinical details.')
            return redirect(
                reverse('health_forms_services:edit_dental_services', kwargs={'pk': dental_form.pk})
                + '?section=chart'
            )
    else:
        preselected = _preselected_patient_from_request(request)
        selected_patient = preselected
        initial = _patient_profile_prefill_payload(preselected) if preselected else None
        personal_form = DentalHealthPersonalInfoForm(initial=initial)

    return render(request, 'health_forms_services/create_dental_services.html', {
        'personal_form': personal_form,
        **_patient_picker_create_context(request, 'dental_services', selected_patient),
    })


@login_required
@require_POST
def review_dental_services(request, pk):
    if request.user.role not in ['staff', 'doctor', 'admin']:
        messages.error(request, 'Permission denied.')
        return redirect('health_forms_services:dental_services_detail', pk=pk)

    dental_form = get_object_or_404(DentalHealthForm, pk=pk)
    form = DentalHealthFormReviewForm(request.POST, instance=dental_form)
    if form.is_valid():
        dental_form = form.save(commit=False)
        dental_form.reviewed_by = request.user
        dental_form.reviewed_at = timezone.now()
        dental_form.save()
        messages.success(request, f'Form status updated to {dental_form.get_status_display()}.')
    else:
        messages.error(request, 'Invalid form data.')
    return redirect('health_forms_services:dental_services_detail', pk=pk)


@login_required
@role_required('staff', 'doctor')
def delete_dental_services(request, pk):
    user = request.user
    if user.role in ['staff', 'doctor', 'admin']:
        dental_form = get_object_or_404(DentalHealthForm, pk=pk)
    else:
        dental_form = get_object_or_404(DentalHealthForm, pk=pk, user=user)

    if dental_form.status not in ['pending', 'rejected', 'incomplete']:
        messages.error(request, 'Cannot delete a form that has been processed.')
        return redirect('health_forms_services:dental_services_detail', pk=pk)

    dental_form.delete()
    messages.success(request, 'Dental services form deleted successfully.')
    return redirect('health_forms_services:dental_services_list')


# ── Dental Chart API (HSS-Form0003) ───────────────────────────────────────


@login_required
@require_GET
@role_required('staff', 'doctor')
def dental_form_chart_api_get(request, pk):
    dental_form = get_object_or_404(DentalHealthForm, pk=pk)
    teeth = dental_form.dental_chart.all().prefetch_related('surfaces')

    teeth_data = []
    for tooth in teeth:
        surfaces_data = [
            {'id': surface.id, 'surface': surface.surface, 'condition': surface.condition}
            for surface in tooth.surfaces.all()
        ]
        teeth_data.append({
            'id': tooth.id,
            'tooth_number': tooth.tooth_number,
            'tooth_type': tooth.tooth_type,
            'condition': tooth.condition,
            'notes': tooth.notes,
            'quadrant': tooth.fdi_quadrant,
            'quadrant_name': tooth.quadrant_name,
            'surfaces': surfaces_data,
        })

    return JsonResponse({
        'teeth': teeth_data,
        'form_id': pk,
        'patient_name': dental_form.get_full_name(),
    })


def _parse_tooth(tooth_number):
    """Return ``(tooth_number, tooth_type)`` or raise ``ValueError``."""
    tooth_number = int(tooth_number)
    quadrant = tooth_number // 10
    position = tooth_number % 10
    if quadrant in (1, 2, 3, 4):
        if position < 1 or position > 8:
            raise ValueError('Invalid tooth position for permanent teeth (1-8)')
        return tooth_number, 'permanent'
    if quadrant in (5, 6, 7, 8):
        if position < 1 or position > 5:
            raise ValueError('Invalid tooth position for primary teeth (1-5)')
        return tooth_number, 'primary'
    raise ValueError('Invalid quadrant')


@login_required
@require_POST
@role_required('staff', 'doctor')
def dental_form_chart_api_update(request, pk):
    dental_form = get_object_or_404(DentalHealthForm, pk=pk)

    if _is_json_request(request):
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)
    else:
        data = request.POST

    tooth_number = data.get('tooth_number')
    if not tooth_number:
        return JsonResponse({'success': False, 'error': 'Tooth number is required'}, status=400)

    try:
        tooth_number, tooth_type = _parse_tooth(tooth_number)
    except (ValueError, TypeError) as exc:
        return JsonResponse({'success': False, 'error': str(exc) or 'Invalid tooth number format'}, status=400)

    tooth, created = DentalFormTooth.objects.update_or_create(
        dental_form=dental_form,
        tooth_number=tooth_number,
        defaults={
            'tooth_type': tooth_type,
            'condition': data.get('condition', 'healthy'),
            'notes': data.get('notes', ''),
        },
    )

    surfaces = ['mesial', 'distal', 'buccal', 'lingual', 'occlusal']
    for surface_name in surfaces:
        surface_value = data.get(f'surface_{surface_name}')
        if surface_value:
            DentalFormToothSurface.objects.update_or_create(
                tooth=tooth,
                surface=surface_name,
                defaults={'condition': surface_value},
            )
        else:
            DentalFormToothSurface.objects.filter(tooth=tooth, surface=surface_name).delete()

    return JsonResponse({
        'success': True,
        'created': created,
        'tooth': {
            'id': tooth.id,
            'tooth_number': tooth.tooth_number,
            'tooth_type': tooth.tooth_type,
            'condition': tooth.condition,
            'notes': tooth.notes,
            'quadrant': tooth.fdi_quadrant,
            'quadrant_name': tooth.quadrant_name,
        },
    })


@login_required
@require_POST
@role_required('staff', 'doctor')
def dental_form_chart_api_bulk_update(request, pk):
    dental_form = get_object_or_404(DentalHealthForm, pk=pk)

    if _is_json_request(request):
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)
    else:
        try:
            tooth_numbers = json.loads(request.POST.get('tooth_numbers_json', '[]'))
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Invalid tooth numbers'}, status=400)
        data = {
            'tooth_numbers': tooth_numbers,
            'condition': request.POST.get('condition', 'healthy'),
            'notes': request.POST.get('notes', ''),
        }

    tooth_numbers = data.get('tooth_numbers', [])
    if not tooth_numbers:
        return JsonResponse({'success': False, 'error': 'No teeth selected'}, status=400)

    condition = data.get('condition', 'healthy')
    notes = data.get('notes', '')

    updated_count = 0
    for tooth_number in tooth_numbers:
        try:
            parsed_number, tooth_type = _parse_tooth(tooth_number)
        except (ValueError, TypeError):
            continue
        DentalFormTooth.objects.update_or_create(
            dental_form=dental_form,
            tooth_number=parsed_number,
            defaults={'tooth_type': tooth_type, 'condition': condition, 'notes': notes},
        )
        updated_count += 1

    return JsonResponse({'success': True, 'updated_count': updated_count})


@login_required
@require_http_methods(["DELETE", "POST"])
@role_required('staff', 'doctor')
def dental_form_chart_api_delete(request, pk, tooth_id):
    dental_form = get_object_or_404(DentalHealthForm, pk=pk)
    tooth = get_object_or_404(DentalFormTooth, pk=tooth_id, dental_form=dental_form)
    tooth_number = tooth.tooth_number
    tooth.delete()
    return JsonResponse({'success': True, 'message': f'Tooth #{tooth_number} deleted successfully.'})


# ═══════════════════════════════════════════════════════════════════════════
# Patient Chart (F-HSS-20-0002) — create, review, delete, entry API
# ═══════════════════════════════════════════════════════════════════════════


@login_required
@require_GET
@role_required('staff', 'doctor')
def search_patients(request):
    """Search patient accounts for picker-first transaction create flows.

    Guests are excluded — use Register guest patient for those accounts.
    """
    from core.guest_auth import exclude_guest_users

    query = (request.GET.get('q') or '').strip()
    if len(query) < 2:
        return JsonResponse({'results': []})

    patients = exclude_guest_users(
        User.objects.filter(role__in=PATIENT_ROLE_VALUES)
        .filter(
            Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(email__icontains=query)
            | Q(patient_profile__patient_id__icontains=query)
        )
        .select_related('patient_profile')
        .order_by('last_name', 'first_name')
    )[:20]
    return JsonResponse({'results': [_patient_search_result_payload(patient) for patient in patients]})


@login_required
@require_GET
@role_required('staff', 'doctor')
def patient_profile_prefill(request, patient_id):
    """Return patient-profile payload for chart/services create auto-prefill."""
    patient = get_object_or_404(
        User.objects.select_related('patient_profile'),
        pk=patient_id,
        role__in=PATIENT_ROLE_VALUES,
    )
    return JsonResponse(_patient_profile_prefill_payload(patient))


@login_required
@role_required('staff', 'doctor')
def create_patient_chart(request):
    selected_patient = None
    if request.method == 'POST':
        form = PatientChartPersonalInfoForm(request.POST)
        selected_patient, selected_patient_error = _resolve_create_patient(request, form)
        if selected_patient_error:
            form.add_error(None, selected_patient_error)
        if form.is_valid() and not selected_patient_error and selected_patient:
            chart = PatientChart(user=selected_patient)
            for field in form.cleaned_data:
                setattr(chart, field, form.cleaned_data[field])
            chart.status = PatientChart.Status.PENDING
            chart.save()
            messages.success(request, 'Patient chart created successfully.')
            return redirect('health_forms_services:patient_chart_detail', pk=chart.pk)
    else:
        preselected = _preselected_patient_from_request(request)
        selected_patient = preselected
        initial = _patient_profile_prefill_payload(preselected) if preselected else None
        form = PatientChartPersonalInfoForm(initial=initial)

    return render(request, 'health_forms_services/create_patient_chart.html', {
        'personal_form': form,
        **_patient_picker_create_context(request, 'patient_chart', selected_patient),
    })


@login_required
@require_POST
def review_patient_chart(request, pk):
    if request.user.role not in ['staff', 'doctor', 'admin']:
        messages.error(request, 'Permission denied.')
        return redirect('health_forms_services:patient_chart_detail', pk=pk)

    chart = get_object_or_404(PatientChart, pk=pk)
    form = PatientChartReviewForm(request.POST, instance=chart)
    if form.is_valid():
        chart = form.save(commit=False)
        chart.reviewed_by = request.user
        chart.reviewed_at = timezone.now()
        chart.save()
        messages.success(request, f'Chart status updated to {chart.get_status_display()}.')
    else:
        messages.error(request, 'Invalid form data.')
    return redirect('health_forms_services:patient_chart_detail', pk=pk)


@login_required
@role_required('staff', 'doctor')
def delete_patient_chart(request, pk):
    user = request.user
    if user.role in ['staff', 'doctor', 'admin']:
        chart = get_object_or_404(PatientChart, pk=pk)
    else:
        chart = get_object_or_404(PatientChart, pk=pk, user=user)

    if chart.status not in ['pending', 'rejected', 'incomplete']:
        messages.error(request, 'Cannot delete a chart that has been processed.')
        return redirect('health_forms_services:patient_chart_detail', pk=pk)

    chart.delete()
    messages.success(request, 'Patient chart deleted successfully.')
    return redirect('health_forms_services:patient_chart_list')


def _chart_entry_json(entry, chart):
    return {
        'id': entry.id,
        'date_and_time': timezone.localtime(entry.date_and_time).strftime('%b %d, %Y %I:%M %p'),
        'date_and_time_input': timezone.localtime(entry.date_and_time).strftime('%Y-%m-%dT%H:%M'),
        'findings': entry.findings,
        'doctors_orders': entry.doctors_orders,
        'recorded_by': entry.recorded_by.get_full_name() if entry.recorded_by else '',
        'update_url': reverse(
            'health_forms_services:update_chart_entry',
            kwargs={'pk': chart.pk, 'entry_id': entry.id},
        ),
        'delete_url': reverse(
            'health_forms_services:delete_chart_entry',
            kwargs={'pk': chart.pk, 'entry_id': entry.id},
        ),
    }


@login_required
@require_POST
@role_required('staff', 'doctor')
def add_chart_entry(request, pk):
    chart = get_object_or_404(PatientChart, pk=pk)
    form = PatientChartEntryForm(request.POST)
    if form.is_valid():
        entry = form.save(commit=False)
        entry.patient_chart = chart
        entry.recorded_by = request.user
        entry.save()
        return JsonResponse({
            'success': True,
            'entry': _chart_entry_json(entry, chart),
        })
    errors = form.errors.get('__all__')
    if errors:
        return JsonResponse({'success': False, 'errors': {'__all__': errors}}, status=400)
    return JsonResponse({'success': False, 'errors': form.errors}, status=400)


@login_required
@require_POST
@role_required('staff', 'doctor')
def update_chart_entry(request, pk, entry_id):
    chart = get_object_or_404(PatientChart, pk=pk)
    entry = get_object_or_404(PatientChartEntry, pk=entry_id, patient_chart=chart)
    form = PatientChartEntryForm(request.POST, instance=entry)
    if form.is_valid():
        entry = form.save()
        return JsonResponse({
            'success': True,
            'entry': _chart_entry_json(entry, chart),
        })
    errors = form.errors.get('__all__')
    if errors:
        return JsonResponse({'success': False, 'errors': {'__all__': errors}}, status=400)
    return JsonResponse({'success': False, 'errors': form.errors}, status=400)


@login_required
@require_POST
@role_required('staff', 'doctor')
def delete_chart_entry(request, pk, entry_id):
    chart = get_object_or_404(PatientChart, pk=pk)
    entry = get_object_or_404(PatientChartEntry, pk=entry_id, patient_chart=chart)
    entry.delete()
    return JsonResponse({'success': True})


# ═══════════════════════════════════════════════════════════════════════════
# Prescriptions (F-HSS-20-0004) — create, review, delete, item API
# ═══════════════════════════════════════════════════════════════════════════


@login_required
@role_required('staff', 'doctor')
def create_prescription(request):
    selected_patient = None
    if request.method == 'POST':
        form = PrescriptionPatientForm(request.POST, user=request.user)
        selected_patient, selected_patient_error = _resolve_create_patient(request, form)
        if selected_patient_error:
            form.add_error(None, selected_patient_error)
        if form.is_valid() and not selected_patient_error and selected_patient:
            prescription = form.save(commit=False)
            prescription.user = selected_patient
            prescription.status = Prescription.Status.INCOMPLETE
            prescription.save()
            messages.success(request, 'Prescription created successfully.')
            return redirect('health_forms_services:prescription_detail', pk=prescription.pk)
    else:
        preselected = _preselected_patient_from_request(request)
        selected_patient = preselected
        if preselected:
            profile = _patient_profile_prefill_payload(preselected)
            initial = {
                'patient_name': profile['name'],
                'age': profile['age'],
                'gender': profile['gender'],
                'address': profile['address'],
            }
        else:
            initial = None
        form = PrescriptionPatientForm(initial=initial, user=request.user)

    return render(request, 'health_forms_services/create_prescription.html', {
        'form': form,
        **_patient_picker_create_context(request, 'prescription', selected_patient),
    })


@login_required
@require_POST
def review_prescription(request, pk):
    if request.user.role not in ['staff', 'doctor', 'admin']:
        messages.error(request, 'Permission denied.')
        return redirect('health_forms_services:prescription_detail', pk=pk)

    prescription = get_object_or_404(Prescription, pk=pk)
    form = PrescriptionReviewForm(request.POST, instance=prescription)
    if form.is_valid():
        prescription = form.save(commit=False)
        prescription.reviewed_by = request.user
        prescription.reviewed_at = timezone.now()
        prescription.save()
        messages.success(request, f'Prescription status updated to {prescription.get_status_display()}.')
    else:
        messages.error(request, 'Invalid form data.')
    return redirect('health_forms_services:prescription_detail', pk=pk)


@login_required
@role_required('staff', 'doctor')
def delete_prescription(request, pk):
    user = request.user
    if user.role in ['staff', 'doctor', 'admin']:
        prescription = get_object_or_404(Prescription, pk=pk)
    else:
        prescription = get_object_or_404(Prescription, pk=pk, user=user)

    if prescription.status not in ['pending', 'rejected', 'incomplete']:
        messages.error(request, 'Cannot delete a prescription that has been processed.')
        return redirect('health_forms_services:prescription_detail', pk=pk)

    prescription.delete()
    messages.success(request, 'Prescription deleted successfully.')
    return redirect('health_forms_services:prescription_list')


@login_required
@require_POST
@role_required('staff', 'doctor')
def add_prescription_item(request, pk):
    prescription = get_object_or_404(Prescription, pk=pk)
    form = PrescriptionItemForm(request.POST)
    if form.is_valid():
        item = form.save(commit=False)
        item.prescription = prescription
        item.save()
        return JsonResponse({
            'success': True,
            'item': {
                'id': item.id,
                'medication_name': item.medication_name,
                'dosage': item.dosage,
                'frequency': item.frequency,
                'duration': item.duration,
                'quantity': item.quantity,
                'instructions': item.instructions,
            },
        })
    return JsonResponse({'success': False, 'errors': form.errors}, status=400)


@login_required
@require_POST
@role_required('staff', 'doctor')
def delete_prescription_item(request, pk, item_id):
    prescription = get_object_or_404(Prescription, pk=pk)
    item = get_object_or_404(PrescriptionItem, pk=item_id, prescription=prescription)
    item.delete()
    return JsonResponse({'success': True})


# ═══════════════════════════════════════════════════════════════════════════
# Document exports (.docx / print)
# ═══════════════════════════════════════════════════════════════════════════


@login_required
@role_required('staff', 'doctor')
def export_health_profile_docx(request, pk):
    form = get_object_or_404(HealthProfileForm, pk=pk)
    doc = generate_health_profile(form)
    filename = f"Health_Profile_{form.last_name}_{form.first_name}.docx"
    return doc_to_response(doc, filename)


@login_required
@role_required('staff', 'doctor')
def export_patient_chart_docx(request, pk):
    chart = get_object_or_404(PatientChart, pk=pk)
    doc = generate_patient_chart(chart)
    filename = f"Patient_Chart_{chart.last_name}_{chart.first_name}.docx"
    return doc_to_response(doc, filename)


@login_required
@role_required('staff', 'doctor')
def export_dental_form_docx(request, pk):
    form = get_object_or_404(DentalServicesRequest, pk=pk)
    doc = generate_dental_services(form)
    filename = f"Dental_Health_Form_{form.last_name}_{form.first_name}.docx"
    return doc_to_response(doc, filename)


@login_required
@role_required('staff', 'doctor')
def export_dental_services_docx(request, pk):
    form = get_object_or_404(DentalHealthForm, pk=pk)
    doc = generate_dental_form(form)
    filename = f"Dental_Services_{form.last_name}_{form.first_name}.docx"
    return doc_to_response(doc, filename)


@login_required
@role_required('staff', 'doctor')
def export_prescription_docx(request, pk):
    """Export Prescription as print-ready HTML mirroring the official .docx template."""
    rx = get_object_or_404(Prescription, pk=pk)
    items = rx.items.all()
    return render(request, 'health_forms_services/prescription_print.html', {
        'prescription': rx,
        'items': items,
    })
