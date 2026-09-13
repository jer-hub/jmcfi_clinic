"""Dental record CRUD views (detail, create, edit, delete)."""

import json

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils import timezone

from appointments.models import Appointment
from core.academic_catalog import patient_catalog_context
from core.decorators import role_required
from core.guest_auth import is_guest_user, resolve_patient_contact_email
from core.roles import is_patient_role
from dental_records.forms import (
    DentalExaminationForm,
    DentalHistoryForm,
    DentalHealthQuestionnaireForm,
    DentalRecordForm,
    DentalSystemsReviewForm,
    DentalVitalSignsForm,
    PediatricDentalHistoryForm,
)
from dental_records.models import (
    DentalExamination,
    DentalHistory,
    DentalHealthQuestionnaire,
    DentalRecord,
    DentalSystemsReview,
    DentalVitalSigns,
    PediatricDentalHistory,
    ProgressNote,
)
from .helpers import (
    _audit_dental,
    _create_dental_clinical_shells,
    _dental_action_bar_context,
)
from medical_records.models import MedicalRecord

User = get_user_model()


@login_required
@role_required('student', 'staff', 'doctor')
def dental_record_detail(request, record_id):
    """View detailed dental record"""
    dental_record = get_object_or_404(DentalRecord, pk=record_id)
    
    # Check if user has permission to view this record
    # Students can only view their own records
    if is_patient_role(request.user.role) and dental_record.patient != request.user:
        return HttpResponseForbidden("You do not have permission to view this dental record.")
    
    # Students cannot view pending records
    if is_patient_role(request.user.role) and dental_record.status != 'completed':
        messages.warning(request, 'This dental record is still being processed. You will be able to view it once it is marked as completed by the clinic staff.')
        return redirect('dental_records:dental_record_list')
    
    _audit_dental(request, dental_record, 'view')
    
    # Get related records if they exist
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
    
    # Get dental chart
    dental_chart = dental_record.dental_chart.all().prefetch_related('surfaces')
    
    # Serialize dental chart data as JSON for interactive chart display
    dental_chart_json = []
    for tooth in dental_chart:
        surfaces_data = []
        for surface in tooth.surfaces.all():
            surfaces_data.append({
                'id': surface.id,
                'surface': surface.surface,
                'condition': surface.condition,
                'notes': surface.notes,
            })
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
    
    context = {
        'dental_record': dental_record,
        'examination': examination,
        'vital_signs': vital_signs,
        'health_questionnaire': health_questionnaire,
        'systems_review': systems_review,
        'dental_history': dental_history,
        'pediatric_history': pediatric_history,
        'dental_chart': dental_chart,
        'dental_chart_json': json.dumps(dental_chart_json),
        'is_pediatric': dental_record.age and dental_record.age < 18,
        'can_resend_guest_intake': (
            is_guest_user(dental_record.patient)
            and dental_record.intake_status == 'awaiting_guest'
        ),
    }
    
    return render(request, 'dental_records/dental_record_detail.html', context)


@login_required
@role_required('doctor')
def dental_record_create(request):
    """Create a new dental record (patient info + consent only).
    
    Clinical details (examination, vital signs, health questionnaire,
    systems review, dental history, pediatric, dental chart, progress notes)
    are filled in on the edit page after creation.
    """
    preselected_patient_id = request.GET.get('patient')
    appointment_id = request.GET.get('appointment')
    preselected_patient = None
    appointment = None
    
    if preselected_patient_id:
        try:
            preselected_patient = User.objects.get(id=preselected_patient_id)
        except User.DoesNotExist:
            preselected_patient = None
    
    if appointment_id:
        try:
            appointment = Appointment.objects.get(id=appointment_id)
            # If we have an appointment, use its patient
            preselected_patient = appointment.patient
        except:
            appointment = None

    if appointment:
        existing_dental_record = DentalRecord.objects.filter(appointment=appointment).first()
        if existing_dental_record:
            messages.warning(request, 'A dental record already exists for this appointment.')
            return redirect('dental_records:dental_record_edit', record_id=existing_dental_record.id)

        if MedicalRecord.objects.filter(appointment=appointment).exists():
            messages.warning(request, 'A medical record already exists for this appointment. Only one record per appointment is allowed.')
            return redirect('appointments:appointment_detail', appointment_id=appointment.id)

    if request.method == 'POST':
        form = DentalRecordForm(request.POST)
        
        if form.is_valid():
            try:
                with transaction.atomic():
                    locked_appointment = None
                    if appointment:
                        locked_appointment = Appointment.objects.select_for_update().get(pk=appointment.pk)

                        if DentalRecord.objects.filter(appointment=locked_appointment).exists():
                            messages.warning(request, 'A dental record already exists for this appointment.')
                            return redirect('appointments:appointment_detail', appointment_id=locked_appointment.id)

                        if MedicalRecord.objects.filter(appointment=locked_appointment).exists():
                            messages.warning(request, 'A medical record already exists for this appointment. Only one record per appointment is allowed.')
                            return redirect('appointments:appointment_detail', appointment_id=locked_appointment.id)

                    dental_record = form.save(commit=False)
                    # Always lock examined_by to the currently logged-in user
                    dental_record.examined_by = request.user
                    dental_record.save()

                    # Set appointment if provided
                    if locked_appointment:
                        dental_record.appointment = locked_appointment
                        dental_record.save()
                    
                    # Create empty related records so the edit page can populate them
                    _create_dental_clinical_shells(dental_record)
                    
                    _audit_dental(request, dental_record, 'create')
                    
                    messages.success(request, 'Dental record created successfully. You can now fill in the clinical details.')
                    return redirect('dental_records:dental_record_edit', record_id=dental_record.id)
            except Exception as e:
                messages.error(request, f'Error creating dental record: {str(e)}')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        initial_data = {
            'date_of_examination': timezone.now().date(),
            'examined_by': request.user if request.user.role in ['staff', 'doctor'] else None,
            'appointment': appointment,
        }
        
        if preselected_patient:
            initial_data['patient'] = preselected_patient
            # Pre-fill patient data if available
            if hasattr(preselected_patient, 'patient_profile') and preselected_patient.patient_profile:
                profile = preselected_patient.patient_profile
                is_employee = bool(getattr(profile, 'is_employee', False))
                guest = is_guest_user(preselected_patient)
                initial_data.update({
                    'middle_name': profile.middle_name or '',
                    'age': profile.age,
                    'gender': profile.gender,
                    'civil_status': profile.civil_status or 'single',
                    'address': profile.address or '',
                    'date_of_birth': profile.date_of_birth,
                    'place_of_birth': profile.place_of_birth or '',
                    'email': preselected_patient.email,
                    'contact_number': profile.phone or '',
                    'telephone_number': profile.telephone_number or '',
                    'designation': 'student' if guest else ('employee' if is_employee else 'student'),
                    'department_college_office': 'Guest' if guest else (profile.department or ''),
                    'course': '' if (guest or is_employee) else (profile.course or ''),
                    'year_level': '' if (guest or is_employee) else (profile.year_level or ''),
                    'guardian_name': profile.emergency_contact or '',
                    'guardian_contact': profile.emergency_phone or '',
                })
            elif hasattr(preselected_patient, 'staff_profile') and preselected_patient.staff_profile:
                profile = preselected_patient.staff_profile
                initial_data.update({
                    'middle_name': profile.middle_name or '',
                    'age': profile.age,
                    'gender': profile.gender,
                    'civil_status': profile.civil_status or 'single',
                    'address': profile.address or '',
                    'date_of_birth': profile.date_of_birth,
                    'place_of_birth': profile.place_of_birth or '',
                    'email': preselected_patient.email,
                    'contact_number': profile.phone or '',
                    'telephone_number': profile.telephone_number or '',
                    'designation': 'employee',
                    'department_college_office': profile.department or '',
                    'course': '',
                    'year_level': '',
                    'guardian_name': profile.emergency_contact or '',
                    'guardian_contact': profile.emergency_phone or '',
                })
        
        form = DentalRecordForm(initial=initial_data)
    
    guest_flag_patient = preselected_patient
    if request.method == 'POST':
        posted_patient_id = request.POST.get('patient')
        if posted_patient_id:
            guest_flag_patient = User.objects.filter(pk=posted_patient_id).first() or guest_flag_patient

    preselected_guest_contact = ''
    if guest_flag_patient and is_guest_user(guest_flag_patient):
        preselected_guest_contact = resolve_patient_contact_email(guest_flag_patient) or ''

    context = {
        'form': form,
        'title': 'Create New Dental Record',
        'preselected_patient': preselected_patient,
        'preselected_patient_is_guest': bool(
            guest_flag_patient and is_guest_user(guest_flag_patient)
        ),
        'preselected_guest_contact': preselected_guest_contact,
        'appointment': appointment,
        **patient_catalog_context(),
    }
    
    return render(request, 'dental_records/dental_record_form.html', context)


@login_required
@role_required('doctor', 'admin')
def dental_record_edit(request, record_id):
    """Edit comprehensive dental record with all sections"""
    dental_record = get_object_or_404(DentalRecord, pk=record_id)
    
    # Get or create related records
    examination, _ = DentalExamination.objects.get_or_create(dental_record=dental_record)
    vital_signs, _ = DentalVitalSigns.objects.get_or_create(dental_record=dental_record)
    health_questionnaire, _ = DentalHealthQuestionnaire.objects.get_or_create(dental_record=dental_record)
    systems_review, _ = DentalSystemsReview.objects.get_or_create(dental_record=dental_record)
    dental_history, _ = DentalHistory.objects.get_or_create(dental_record=dental_record)
    
    # Check if patient is pediatric (under 18)
    is_pediatric = dental_record.age and dental_record.age < 18
    if is_pediatric:
        pediatric_history, _ = PediatricDentalHistory.objects.get_or_create(dental_record=dental_record)
    else:
        try:
            pediatric_history = dental_record.pediatric_history
        except PediatricDentalHistory.DoesNotExist:
            pediatric_history = None
    
    edit_sections = [
        'demographics', 'questionnaire', 'systems', 'history', 'exam', 'vitals', 'chart', 'notes',
    ]
    if is_pediatric:
        edit_sections.insert(4, 'pediatric')
    active_section = request.GET.get('section', 'demographics')
    if active_section not in edit_sections:
        active_section = 'demographics'

    if request.method == 'POST':
        # Determine which form was submitted
        form_type = request.POST.get('form_type')
        is_ajax = (
            request.headers.get('X-Requested-With') == 'XMLHttpRequest'
            or request.headers.get('HX-Request')
        )

        # form_type (POST) → data-section (tab key)
        section_by_form_type = {
            'demographics': 'demographics',
            'health_questionnaire': 'questionnaire',
            'systems_review': 'systems',
            'dental_history': 'history',
            'pediatric_history': 'pediatric',
            'examination': 'exam',
            'vital_signs': 'vitals',
        }
        
        # Mapping of form_type → (FormClass, instance, success_message)
        form_map = {
            'demographics': (DentalRecordForm, dental_record, 'Patient demographics updated successfully.'),
            'examination': (DentalExaminationForm, examination, 'Examination findings updated successfully.'),
            'vital_signs': (DentalVitalSignsForm, vital_signs, 'Vital signs updated successfully.'),
            'health_questionnaire': (DentalHealthQuestionnaireForm, health_questionnaire, 'Health questionnaire updated successfully.'),
            'systems_review': (DentalSystemsReviewForm, systems_review, 'Systems review updated successfully.'),
            'dental_history': (DentalHistoryForm, dental_history, 'Dental history updated successfully.'),
        }
        if is_pediatric:
            form_map['pediatric_history'] = (PediatricDentalHistoryForm, pediatric_history, 'Pediatric history updated successfully.')
        
        if form_type in form_map:
            FormClass, instance, success_msg = form_map[form_type]
            form = FormClass(request.POST, instance=instance)
            if form.is_valid():
                form.save()
                _audit_dental(request, dental_record, 'edit', section=form_type)
                if is_ajax:
                    section_key = section_by_form_type.get(form_type, form_type)
                    payload = {
                        'success': True,
                        'section': section_key,
                        'message': success_msg,
                    }
                    if form_type == 'demographics':
                        dental_record.refresh_from_db()
                        payload['action_bar_html'] = render_to_string(
                            'dental_records/_dental_edit_action_bar_inner.html',
                            _dental_action_bar_context(dental_record),
                            request=request,
                        )
                    return JsonResponse(payload)
                messages.success(request, success_msg)
                return redirect('dental_records:dental_record_edit', record_id=record_id)
            elif is_ajax:
                errors = {
                    field: [str(error) for error in error_list]
                    for field, error_list in form.errors.items()
                }
                return JsonResponse({'success': False, 'errors': errors}, status=400)
        
        elif form_type == 'progress_note':
            progress_date = request.POST.get('progress_date')
            progress_procedure = request.POST.get('progress_procedure', '').strip()
            progress_remarks = request.POST.get('progress_remarks', '').strip()
            
            if progress_procedure:
                ProgressNote.objects.create(
                    dental_record=dental_record,
                    date=progress_date or timezone.now().date(),
                    procedure_done=progress_procedure,
                    dentist=request.user,
                    remarks=progress_remarks,
                )
                _audit_dental(
                    request,
                    dental_record,
                    'edit',
                    subresource='progress_note',
                    operation='create',
                )
                messages.success(request, 'Progress note added successfully.')
            else:
                messages.error(request, 'Please enter the procedure done.')
            return redirect('dental_records:dental_record_edit', record_id=record_id)
    
    # Initialize all forms for GET request
    demographics_form = DentalRecordForm(instance=dental_record)
    examination_form = DentalExaminationForm(instance=examination)
    vital_signs_form = DentalVitalSignsForm(instance=vital_signs)
    health_questionnaire_form = DentalHealthQuestionnaireForm(instance=health_questionnaire)
    systems_review_form = DentalSystemsReviewForm(instance=systems_review)
    dental_history_form = DentalHistoryForm(instance=dental_history)
    pediatric_history_form = PediatricDentalHistoryForm(instance=pediatric_history) if is_pediatric else None
    
    # Get dental chart
    dental_chart = dental_record.dental_chart.all().order_by('tooth_number')
    
    # Serialize progress notes for Alpine.js
    progress_notes_qs = dental_record.progress_notes.select_related('dentist').all()
    progress_notes_json = json.dumps([
        {
            'id': n.id,
            'date': n.date.strftime('%Y-%m-%d'),
            'date_display': n.date.strftime('%b %d, %Y'),
            'procedure_done': n.procedure_done,
            'dentist': n.dentist.get_full_name() if n.dentist else '\u2014',
            'remarks': n.remarks or '\u2014',
        }
        for n in progress_notes_qs
    ])
    
    context = {
        'dental_record': dental_record,
        'appointment': dental_record.appointment,
        'progress_notes_json': progress_notes_json,
        'demographics_form': demographics_form,
        'examination_form': examination_form,
        'vital_signs_form': vital_signs_form,
        'health_questionnaire_form': health_questionnaire_form,
        'systems_review_form': systems_review_form,
        'dental_history_form': dental_history_form,
        'pediatric_history_form': pediatric_history_form,
        'dental_chart': dental_chart,
        'is_pediatric': is_pediatric,
        'active_section': active_section,
        'title': f'Edit Dental Record - {dental_record.patient.get_full_name()}',
        **_dental_action_bar_context(dental_record),
        **patient_catalog_context(),
    }
    
    return render(request, 'dental_records/dental_record_edit.html', context)


@login_required
@role_required('doctor')
def dental_record_delete(request, record_id):
    """Delete a dental record"""
    dental_record = get_object_or_404(DentalRecord, pk=record_id)
    
    if request.method == 'POST':
        patient_name = dental_record.patient.get_full_name()
        exam_date = (
            dental_record.date_of_examination.isoformat()
            if dental_record.date_of_examination
            else ''
        )
        _audit_dental(
            request,
            dental_record,
            'delete',
            patient_name=patient_name,
            exam_date=exam_date,
        )
        dental_record.delete()
        messages.success(request, f'Dental record for {patient_name} deleted successfully.')
        return redirect('dental_records:dental_record_list')
    
    return redirect('dental_records:dental_record_detail', record_id=record_id)
