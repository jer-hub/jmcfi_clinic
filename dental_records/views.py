"""
Dental Record Views for Jose Maria College Foundation, Inc.
Handles dental record creation, viewing, and management
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction, models
from django.http import JsonResponse, HttpResponseForbidden
from django.core.paginator import Paginator
from django.utils import timezone
from django.contrib.auth import get_user_model
from datetime import datetime

from .models import (
    DentalRecord, DentalExamination, DentalVitalSigns,
    DentalHealthQuestionnaire, DentalSystemsReview,
    DentalHistory, PediatricDentalHistory, DentalChart,
    ToothSurface, DentalChartSnapshot, ProgressNote
)
from .forms import (
    DentalRecordForm, StudentDentalIntakeForm, DentalExaminationForm, DentalVitalSignsForm,
    DentalHealthQuestionnaireForm, DentalSystemsReviewForm,
    DentalHistoryForm, PediatricDentalHistoryForm, ProgressNoteForm
)
import json
from core.decorators import role_required
from appointments.models import Appointment
from medical_records.models import MedicalRecord

User = get_user_model()

@login_required
def dental_record_list(request):
    """List all dental records with search and filtering"""
    # Students can only see their own records
    if request.user.role == 'student':
        dental_records = DentalRecord.objects.filter(
            patient=request.user
        ).select_related('patient', 'examined_by', 'appointment')
    else:
        # Staff, doctors, and admins can see all records
        dental_records = DentalRecord.objects.select_related('patient', 'examined_by', 'appointment').all()
    
    # Search functionality
    search_query = request.GET.get('search', '')
    if search_query:
        dental_records = dental_records.filter(
            patient__first_name__icontains=search_query
        ) | dental_records.filter(
            patient__last_name__icontains=search_query
        ) | dental_records.filter(
            patient__email__icontains=search_query
        )
    
    # Filter by date
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    if date_from:
        dental_records = dental_records.filter(date_of_examination__gte=date_from)
    if date_to:
        dental_records = dental_records.filter(date_of_examination__lte=date_to)

    # Include dental appointments still waiting doctor confirmation and not yet converted to records
    pending_dental_appointments = Appointment.objects.filter(
        appointment_type='dental',
        status__in=['pending', 'cancelled']
    ).exclude(
        dental_records__isnull=False
    ).select_related('student', 'doctor').distinct()

    if request.user.role == 'student':
        pending_dental_appointments = pending_dental_appointments.filter(student=request.user)

    if search_query:
        pending_dental_appointments = pending_dental_appointments.filter(
            models.Q(student__first_name__icontains=search_query)
            | models.Q(student__last_name__icontains=search_query)
            | models.Q(student__email__icontains=search_query)
        )

    if date_from:
        pending_dental_appointments = pending_dental_appointments.filter(date__gte=date_from)
    if date_to:
        pending_dental_appointments = pending_dental_appointments.filter(date__lte=date_to)

    # Status totals for the currently filtered result set
    status_totals = {
        'pending': dental_records.filter(status='pending').count(),
        'completed': dental_records.filter(status='completed').count(),
    }
    
    # Merge records + appointment-only rows, then sort by latest date/time
    table_rows = []

    for record in dental_records:
        if record.appointment and record.appointment.time:
            row_time = record.appointment.time
        else:
            row_time = record.created_at.time()

        table_rows.append({
            'row_type': 'record',
            'record': record,
            'sort_datetime': datetime.combine(record.date_of_examination, row_time),
        })

    for appointment in pending_dental_appointments:
        table_rows.append({
            'row_type': 'appointment',
            'appointment': appointment,
            'sort_datetime': datetime.combine(appointment.date, appointment.time),
        })

    table_rows.sort(key=lambda row: row['sort_datetime'], reverse=True)

    # Pagination
    paginator = Paginator(table_rows, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'status_totals': status_totals,
        'search_query': search_query,
        'date_from': date_from,
        'date_to': date_to,
    }
    
    return render(request, 'dental_records/dental_record_list.html', context)


@login_required
def dental_record_detail(request, record_id):
    """View detailed dental record"""
    dental_record = get_object_or_404(DentalRecord, pk=record_id)
    
    # Check if user has permission to view this record
    # Students can only view their own records
    if request.user.role == 'student' and dental_record.patient != request.user:
        return HttpResponseForbidden("You do not have permission to view this dental record.")
    
    # Students cannot view pending records
    if request.user.role == 'student' and dental_record.status != 'completed':
        messages.warning(request, 'This dental record is still being processed. You will be able to view it once it is marked as completed by the clinic staff.')
        return redirect('dental_records:dental_record_list')
    
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
    }
    
    return render(request, 'dental_records/dental_record_detail.html', context)


@login_required
@role_required('admin', 'staff', 'doctor')
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
            preselected_patient = appointment.student
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
                    DentalExamination.objects.create(dental_record=dental_record)
                    DentalVitalSigns.objects.create(dental_record=dental_record)
                    DentalHealthQuestionnaire.objects.create(dental_record=dental_record)
                    DentalSystemsReview.objects.create(dental_record=dental_record)
                    DentalHistory.objects.create(dental_record=dental_record)
                    
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
            if hasattr(preselected_patient, 'student_profile') and preselected_patient.student_profile:
                profile = preselected_patient.student_profile
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
                    'designation': 'student',
                    'department_college_office': profile.department or '',
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
                    'guardian_name': profile.emergency_contact or '',
                    'guardian_contact': profile.emergency_phone or '',
                })
        
        form = DentalRecordForm(initial=initial_data)
    
    context = {
        'form': form,
        'title': 'Create New Dental Record',
        'preselected_patient': preselected_patient,
        'appointment': appointment,
    }
    
    return render(request, 'dental_records/dental_record_form.html', context)


@login_required
@role_required('admin', 'staff', 'doctor')
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
    
    if request.method == 'POST':
        # Determine which form was submitted
        form_type = request.POST.get('form_type')
        is_htmx = request.headers.get('HX-Request')
        
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
                if is_htmx:
                    return JsonResponse({'success': True, 'message': success_msg})
                messages.success(request, success_msg)
                return redirect('dental_records:dental_record_edit', record_id=record_id)
            elif is_htmx:
                return JsonResponse({'success': False, 'errors': form.errors}, status=400)
        
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
        'title': f'Edit Dental Record - {dental_record.patient.get_full_name()}',
    }
    
    return render(request, 'dental_records/dental_record_edit.html', context)


@login_required
@role_required('admin', 'staff', 'doctor')
def complete_appointment(request, record_id):
    """Mark the associated appointment as completed"""
    dental_record = get_object_or_404(DentalRecord, pk=record_id)
    
    if not dental_record.appointment:
        messages.error(request, 'No appointment associated with this dental record.')
        return redirect('dental_records:dental_record_edit', record_id=record_id)
    
    if dental_record.appointment.status != 'completed':
        dental_record.appointment.status = 'completed'
        dental_record.appointment.save()
        messages.success(request, 'Appointment marked as completed successfully.')
    else:
        messages.info(request, 'Appointment is already completed.')
    
    return redirect('dental_records:dental_record_edit', record_id=record_id)


@login_required
@role_required('admin', 'staff', 'doctor')
def mark_record_completed(request, record_id):
    """Toggle dental record status between pending and completed"""
    dental_record = get_object_or_404(DentalRecord, pk=record_id)
    
    if request.method == 'POST':
        new_status = request.POST.get('status', 'completed')
        if new_status in ('pending', 'completed'):
            with transaction.atomic():
                dental_record.status = new_status
                dental_record.save(update_fields=['status', 'updated_at'])

                appointment_marked_completed = False
                if (
                    new_status == 'completed'
                    and dental_record.appointment
                    and dental_record.appointment.status != 'completed'
                ):
                    dental_record.appointment.status = 'completed'
                    dental_record.appointment.save(update_fields=['status'])
                    appointment_marked_completed = True

            if new_status == 'completed':
                if appointment_marked_completed:
                    messages.success(request, 'Dental record and associated appointment marked as completed.')
                else:
                    messages.success(request, 'Dental record marked as completed. The patient can now view their record.')
            else:
                messages.info(request, 'Dental record reverted to pending. The patient will not be able to view details.')
    
    return redirect('dental_records:dental_record_edit', record_id=record_id)


@login_required
@role_required('admin', 'staff', 'doctor')
def dental_chart_add_tooth(request, record_id):
    """Add or update a tooth in the dental chart"""
    dental_record = get_object_or_404(DentalRecord, pk=record_id)
    
    if request.method == 'POST':
        tooth_number = request.POST.get('tooth_number')
        
        # Check if tooth already exists
        tooth, created = DentalChart.objects.get_or_create(
            dental_record=dental_record,
            tooth_number=tooth_number,
            defaults={
                'tooth_type': request.POST.get('tooth_type', 'permanent'),
                'condition': request.POST.get('condition', 'healthy'),
                'notes': request.POST.get('notes', '')
            }
        )
        
        if not created:
            # Update existing tooth
            tooth.tooth_type = request.POST.get('tooth_type', tooth.tooth_type)
            tooth.condition = request.POST.get('condition', tooth.condition)
            tooth.notes = request.POST.get('notes', tooth.notes)
            tooth.save()
        
        # If HTMX request, return partial template without adding Django messages
        if request.headers.get('HX-Request'):
            dental_chart = dental_record.dental_chart.prefetch_related('surfaces').order_by('tooth_number')
            return render(request, 'dental_records/partials/dental_chart_table.html', {
                'dental_chart': dental_chart,
                'dental_record': dental_record,
            })
        
        # Only add messages for non-HTMX requests
        messages.success(request, f'Tooth #{tooth_number} {"added" if created else "updated"} successfully.')
        return redirect('dental_records:dental_record_edit', record_id=record_id)
    
    return redirect('dental_records:dental_record_edit', record_id=record_id)


@login_required
@role_required('admin', 'staff', 'doctor')
def dental_chart_delete_tooth(request, record_id, tooth_id):
    """Remove a tooth from the dental chart"""
    dental_record = get_object_or_404(DentalRecord, pk=record_id)
    tooth = get_object_or_404(DentalChart, pk=tooth_id, dental_record=dental_record)
    
    tooth_number = tooth.tooth_number
    tooth.delete()
    
    # If HTMX request, return the HTMX response template
    if request.headers.get('HX-Request'):
        teeth = DentalChart.objects.filter(dental_record=dental_record).prefetch_related('surfaces').order_by('tooth_number')
        
        # Build chart_data for JavaScript
        chart_data = {}
        for t in teeth:
            chart_data[str(t.tooth_number)] = {
                'id': t.id,
                'condition': t.condition,
                'notes': t.notes or '',
                'tooth_type': t.tooth_type,
            }
        
        response = render(request, 'dental_records/partials/dental_chart_htmx_response.html', {
            'dental_record': dental_record,
            'teeth': teeth,
            'chart_data': json.dumps(chart_data),
            'message': f'Tooth #{tooth_number} removed from chart.',
        })
        # Add HX-Trigger header to show message and update chart
        response['HX-Trigger'] = json.dumps({
            'showToothMessage': f'Tooth #{tooth_number} removed from chart.',
            'updateChartData': chart_data
        })
        return response
    
    # Only add messages for non-HTMX requests
    messages.success(request, f'Tooth #{tooth_number} removed from chart.')
    return redirect('dental_records:dental_record_edit', record_id=record_id)


@login_required
@role_required('admin', 'staff', 'doctor')
def dental_record_delete(request, record_id):
    """Delete a dental record"""
    dental_record = get_object_or_404(DentalRecord, pk=record_id)
    
    if request.method == 'POST':
        patient_name = dental_record.patient.get_full_name()
        dental_record.delete()
        messages.success(request, f'Dental record for {patient_name} deleted successfully.')
        return redirect('dental_records:dental_record_list')
    
    return redirect('dental_records:dental_record_detail', record_id=record_id)





# ============================================
# Student Self-Intake View
# ============================================

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
        student=request.user,
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
                        student=request.user,
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
            if hasattr(request.user, 'student_profile') and request.user.student_profile:
                profile = request.user.student_profile
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
                    'department_college_office': (
                        f"{profile.course or ''} - {profile.department or ''}".strip(' -')
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


# ============================================
# Progress Notes API
# ============================================

@login_required
@role_required('admin', 'staff', 'doctor')
def progress_note_list(request, record_id):
    """Return all progress notes for a dental record as JSON."""
    dental_record = get_object_or_404(DentalRecord, pk=record_id)
    notes = dental_record.progress_notes.select_related('dentist').all()
    data = [
        {
            'id': n.id,
            'date': n.date.strftime('%Y-%m-%d'),
            'date_display': n.date.strftime('%b %d, %Y'),
            'procedure_done': n.procedure_done,
            'dentist': n.dentist.get_full_name() if n.dentist else '—',
            'remarks': n.remarks or '—',
        }
        for n in notes
    ]
    return JsonResponse({'notes': data})


@login_required
@role_required('admin', 'staff', 'doctor')
def progress_note_create(request, record_id):
    """Create a progress note via JSON POST. Returns the new note."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required'}, status=405)

    dental_record = get_object_or_404(DentalRecord, pk=record_id)

    # Accept both form-encoded and JSON body
    if request.content_type and 'json' in request.content_type:
        import json as _json
        try:
            body = _json.loads(request.body)
        except _json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)
        date_val = body.get('date', '')
        procedure = body.get('procedure_done', '').strip()
        remarks = body.get('remarks', '').strip()
    else:
        date_val = request.POST.get('date', '')
        procedure = request.POST.get('procedure_done', '').strip()
        remarks = request.POST.get('remarks', '').strip()

    if not procedure:
        return JsonResponse({'success': False, 'error': 'Procedure done is required.'}, status=400)

    note = ProgressNote.objects.create(
        dental_record=dental_record,
        date=date_val or timezone.now().date(),
        procedure_done=procedure,
        dentist=request.user,
        remarks=remarks,
    )
    return JsonResponse({
        'success': True,
        'note': {
            'id': note.id,
            'date': note.date.strftime('%Y-%m-%d'),
            'date_display': note.date.strftime('%b %d, %Y'),
            'procedure_done': note.procedure_done,
            'dentist': request.user.get_full_name(),
            'remarks': note.remarks or '—',
        }
    })


@login_required
@role_required('admin', 'staff', 'doctor')
def progress_note_delete(request, record_id, note_id):
    """Delete a progress note. Returns JSON."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required'}, status=405)

    dental_record = get_object_or_404(DentalRecord, pk=record_id)
    note = get_object_or_404(ProgressNote, pk=note_id, dental_record=dental_record)
    note.delete()
    return JsonResponse({'success': True})


@login_required
@role_required('admin', 'staff', 'doctor')
def dental_record_export_json(request, record_id):
    """Export dental record as JSON for AI processing or backup"""
    dental_record = get_object_or_404(DentalRecord, pk=record_id)
    
    # Build comprehensive JSON structure
    data = {
        "demographics": {
            "lastName": dental_record.patient.last_name,
            "firstName": dental_record.patient.first_name,
            "middleName": dental_record.middle_name,
            "age": dental_record.age,
            "gender": dental_record.gender,
            "civilStatus": dental_record.civil_status,
            "address": dental_record.address,
            "dateOfBirth": dental_record.date_of_birth.isoformat() if dental_record.date_of_birth else None,
            "placeOfBirth": dental_record.place_of_birth,
            "email": dental_record.email,
            "contactNumber": dental_record.contact_number,
            "telephoneNumber": dental_record.telephone_number,
            "designation": dental_record.designation,
            "departmentCollegeOffice": dental_record.department_college_office,
            "emergencyContact": {
                "name": dental_record.guardian_name,
                "contactNumber": dental_record.guardian_contact
            },
            "dateOfExamination": dental_record.date_of_examination.isoformat() if dental_record.date_of_examination else None
        }
    }
    
    # Add health questionnaire
    try:
        hq = dental_record.health_questionnaire
        data["healthQuestionnaire"] = {
            "lastHospitalConfinement": {
                "date": hq.last_hospital_date.isoformat() if hq.last_hospital_date else None,
                "reason": hq.last_hospital_reason
            },
            "lastDoctorConsultation": {
                "date": hq.last_doctor_date.isoformat() if hq.last_doctor_date else None,
                "reason": hq.last_doctor_reason
            },
            "doctorCareSupervision": {
                "answer": hq.doctor_care_2years,
                "reason": hq.doctor_care_reason
            },
            "excessiveBleeding": {
                "answer": hq.excessive_bleeding,
                "when": hq.excessive_bleeding_when
            },
            "medicationsLast2Years": {
                "answer": hq.medications_2years,
                "for": hq.medications_for
            },
            "easilyExhausted": hq.easily_exhausted,
            "swollenAnkles": hq.swollen_ankles,
            "moreThan2Pillows": {
                "answer": hq.more_than_2_pillows,
                "why": hq.pillows_reason
            },
            "tumorCancerDiagnosis": {
                "answer": hq.tumor_cancer,
                "when": hq.tumor_cancer_when
            },
            "forWomen": {
                "pregnant": {
                    "answer": hq.is_pregnant,
                    "months": hq.pregnancy_months
                },
                "birthControlPills": {
                    "answer": hq.birth_control_pills,
                    "specify": hq.birth_control_specify
                },
                "anticipatePregnancy": hq.anticipate_pregnancy,
                "havingPeriod": hq.having_period
            }
        }
    except DentalHealthQuestionnaire.DoesNotExist:
        data["healthQuestionnaire"] = {}
    
    # Add systems review
    try:
        sr = dental_record.systems_review
        conditions = []
        for field in sr._meta.fields:
            if isinstance(field, models.BooleanField) and getattr(sr, field.name):
                conditions.append(field.name)
        data["systemsReview"] = conditions
        if sr.allergies:
            data["allergies"] = sr.allergies
        if sr.other_conditions:
            data["otherConditions"] = sr.other_conditions
    except DentalSystemsReview.DoesNotExist:
        data["systemsReview"] = []
    
    # Add vital signs
    try:
        vs = dental_record.vital_signs
        data["vitalSigns"] = {
            "bloodPressure": vs.blood_pressure,
            "pulseRate": vs.pulse_rate,
            "respiratoryRate": vs.respiratory_rate,
            "temperature": vs.temperature,
            "weight": vs.weight,
            "height": vs.height
        }
    except DentalVitalSigns.DoesNotExist:
        data["vitalSigns"] = {}
    
    data["consentSigned"] = dental_record.consent_signed
    data["signatureDate"] = dental_record.consent_date.isoformat() if dental_record.consent_date else None
    
    return JsonResponse(data, json_dumps_params={'indent': 2})


@login_required
@role_required('admin', 'staff', 'doctor')
def search_patients(request):
    """Search for patients by name, email, or ID for autocomplete"""
    query = request.GET.get('q', '').strip()
    
    if len(query) < 2:
        return JsonResponse({'results': []})
    
    # Search users by first name, last name, or email
    patients = User.objects.filter(
        models.Q(first_name__icontains=query) |
        models.Q(last_name__icontains=query) |
        models.Q(email__icontains=query) |
        models.Q(id__icontains=query)
    )[:20]  # Limit to 20 results
    
    results = []
    for patient in patients:
        # Get profile information if available
        profile_info = ""
        try:
            if hasattr(patient, 'studentprofile'):
                profile = patient.studentprofile
                profile_info = f"Student - {profile.course or 'N/A'}"
            elif hasattr(patient, 'staffprofile'):
                profile = patient.staffprofile
                profile_info = f"Staff - {profile.department or 'N/A'}"
        except:
            profile_info = patient.get_role_display() if hasattr(patient, 'get_role_display') else ""
        
        results.append({
            'id': patient.id,
            'text': f"{patient.last_name}, {patient.first_name}",
            'email': patient.email,
            'role': profile_info,
            'display': f"{patient.last_name}, {patient.first_name} - {patient.email} ({profile_info})"
        })
    
    return JsonResponse({'results': results})


@login_required
@role_required('admin', 'staff', 'doctor')
def get_patient_profile(request, patient_id):
    """Get full patient profile data for auto-filling dental forms"""
    patient = get_object_or_404(User, pk=patient_id)
    
    from datetime import date
    
    data = {
        'first_name': patient.first_name,
        'last_name': patient.last_name,
        'email': patient.email,
        'student_id': '',
        'middle_name': '',
        'gender': '',
        'civil_status': '',
        'date_of_birth': '',
        'place_of_birth': '',
        'age': '',
        'address': '',
        'contact_number': '',
        'telephone_number': '',
        'designation': '',
        'department_college_office': '',
        'guardian_name': '',
        'guardian_contact': '',
    }
    
    # Get profile data based on user role
    try:
        if hasattr(patient, 'student_profile'):
            profile = patient.student_profile
            data.update({
                'student_id': profile.student_id or '',
                'middle_name': profile.middle_name or '',
                'gender': profile.gender or '',
                'civil_status': profile.civil_status or '',
                'date_of_birth': profile.date_of_birth.isoformat() if profile.date_of_birth else '',
                'place_of_birth': profile.place_of_birth or '',
                'age': profile.age or '',
                'address': profile.address or '',
                'contact_number': profile.phone or '',
                'telephone_number': profile.telephone_number or '',
                'designation': 'student',
                'department_college_office': f"{profile.course or ''} - {profile.department or ''}".strip(' -'),
                'guardian_name': profile.emergency_contact or '',
                'guardian_contact': profile.emergency_phone or '',
            })
            
            # Calculate age from date of birth if not set
            if profile.date_of_birth and not data['age']:
                today = date.today()
                dob = profile.date_of_birth
                age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
                data['age'] = age
                
        elif hasattr(patient, 'staff_profile'):
            profile = patient.staff_profile
            data.update({
                'student_id': profile.staff_id or '',  # Use staff_id for the student_id field
                'middle_name': profile.middle_name or '',
                'gender': profile.gender or '',
                'civil_status': profile.civil_status or '',
                'date_of_birth': profile.date_of_birth.isoformat() if profile.date_of_birth else '',
                'place_of_birth': profile.place_of_birth or '',
                'age': profile.age or '',
                'address': profile.address or '',
                'contact_number': profile.phone or '',
                'telephone_number': profile.telephone_number or '',
                'designation': 'employee',
                'department_college_office': profile.department or '',
                'guardian_name': profile.emergency_contact or '',
                'guardian_contact': profile.emergency_phone or '',
            })
            
            # Calculate age from date of birth if not set
            if profile.date_of_birth and not data['age']:
                today = date.today()
                dob = profile.date_of_birth
                age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
                data['age'] = age
    except Exception as e:
        # Profile doesn't exist or error occurred
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error fetching profile for patient {patient_id}: {str(e)}")
    
    return JsonResponse(data)


# =====================================
# Interactive Dental Chart API Views
# =====================================

@login_required
@role_required('admin', 'staff', 'doctor')
def dental_chart_api_get(request, record_id):
    """Get all teeth data for the dental chart as JSON"""
    dental_record = get_object_or_404(DentalRecord, pk=record_id)
    
    teeth = dental_record.dental_chart.all().prefetch_related('surfaces')
    
    teeth_data = []
    for tooth in teeth:
        surfaces_data = []
        for surface in tooth.surfaces.all():
            surfaces_data.append({
                'id': surface.id,
                'surface': surface.surface,
                'condition': surface.condition,
                'notes': surface.notes,
            })
        
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
        'record_id': record_id,
        'patient_name': dental_record.patient.get_full_name(),
    })


@login_required
@role_required('admin', 'staff', 'doctor')
def dental_chart_api_update_tooth(request, record_id):
    """Add or update a tooth in the dental chart via HTMX or AJAX"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
    
    dental_record = get_object_or_404(DentalRecord, pk=record_id)
    is_htmx = request.headers.get('HX-Request')
    
    # Parse data from either JSON or form data
    if request.content_type == 'application/json':
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            if is_htmx:
                return render(request, 'dental_records/partials/dental_chart_message.html', {
                    'message': 'Invalid JSON data',
                    'message_type': 'error'
                })
            return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)
    else:
        data = request.POST
    
    tooth_number = data.get('tooth_number')
    tooth_type = data.get('tooth_type', 'permanent')
    condition = data.get('condition', 'healthy')
    notes = data.get('notes', '')
    
    if not tooth_number:
        if is_htmx:
            return render(request, 'dental_records/partials/dental_chart_message.html', {
                'message': 'Tooth number is required',
                'message_type': 'error'
            })
        return JsonResponse({'success': False, 'error': 'Tooth number is required'}, status=400)
    
    # Validate tooth number for FDI notation
    try:
        tooth_number = int(tooth_number)
        quadrant = tooth_number // 10
        position = tooth_number % 10
        
        # Permanent teeth: quadrants 1-4, positions 1-8
        # Primary teeth: quadrants 5-8, positions 1-5
        if quadrant in [1, 2, 3, 4]:
            if position < 1 or position > 8:
                error_msg = 'Invalid tooth position for permanent teeth (1-8)'
                if is_htmx:
                    return render(request, 'dental_records/partials/dental_chart_message.html', {
                        'message': error_msg,
                        'message_type': 'error'
                    })
                return JsonResponse({'success': False, 'error': error_msg}, status=400)
            tooth_type = 'permanent'
        elif quadrant in [5, 6, 7, 8]:
            if position < 1 or position > 5:
                error_msg = 'Invalid tooth position for primary teeth (1-5)'
                if is_htmx:
                    return render(request, 'dental_records/partials/dental_chart_message.html', {
                        'message': error_msg,
                        'message_type': 'error'
                    })
                return JsonResponse({'success': False, 'error': error_msg}, status=400)
            tooth_type = 'primary'
        else:
            error_msg = 'Invalid quadrant (1-4 for permanent, 5-8 for primary)'
            if is_htmx:
                return render(request, 'dental_records/partials/dental_chart_message.html', {
                    'message': error_msg,
                    'message_type': 'error'
                })
            return JsonResponse({'success': False, 'error': error_msg}, status=400)
    except (ValueError, TypeError):
        error_msg = 'Invalid tooth number format'
        if is_htmx:
            return render(request, 'dental_records/partials/dental_chart_message.html', {
                'message': error_msg,
                'message_type': 'error'
            })
        return JsonResponse({'success': False, 'error': error_msg}, status=400)
    
    # Create or update the tooth
    tooth, created = DentalChart.objects.update_or_create(
        dental_record=dental_record,
        tooth_number=tooth_number,
        defaults={
            'tooth_type': tooth_type,
            'condition': condition,
            'notes': notes,
        }
    )
    
    # Handle surface conditions if provided
    surfaces = ['mesial', 'distal', 'buccal', 'lingual', 'occlusal']
    for surface_name in surfaces:
        surface_value = data.get(f'surface_{surface_name}')
        if surface_value:
            ToothSurface.objects.update_or_create(
                tooth=tooth,
                surface=surface_name,
                defaults={'condition': surface_value}
            )
        else:
            # Remove surface if not set
            ToothSurface.objects.filter(tooth=tooth, surface=surface_name).delete()
    
    # Return HTMX response with updated table and chart data
    if is_htmx:
        teeth = DentalChart.objects.filter(dental_record=dental_record).prefetch_related('surfaces').order_by('tooth_number')
        
        # Build chart_data for JavaScript
        chart_data = {}
        for t in teeth:
            chart_data[str(t.tooth_number)] = {
                'id': t.id,
                'condition': t.condition,
                'notes': t.notes or '',
                'tooth_type': t.tooth_type,
            }
        
        response = render(request, 'dental_records/partials/dental_chart_htmx_response.html', {
            'dental_record': dental_record,
            'teeth': teeth,
            'chart_data': json.dumps(chart_data),
            'message': f'Tooth #{tooth_number} {"added" if created else "updated"} successfully!',
        })
        # Add HX-Trigger header to close modal and show message
        response['HX-Trigger'] = json.dumps({
            'closeToothModal': True,
            'showToothMessage': f'Tooth #{tooth_number} {"added" if created else "updated"} successfully!',
            'updateChartData': chart_data
        })
        return response
    
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
        }
    })


@login_required
@role_required('admin', 'staff', 'doctor')
def dental_chart_api_delete_tooth(request, record_id, tooth_id):
    """Delete a tooth from the dental chart via HTMX or AJAX (supports DELETE method)"""
    dental_record = get_object_or_404(DentalRecord, pk=record_id)
    tooth = get_object_or_404(DentalChart, pk=tooth_id, dental_record=dental_record)
    is_htmx = request.headers.get('HX-Request')
    
    tooth_number = tooth.tooth_number
    tooth.delete()
    
    if is_htmx:
        teeth = DentalChart.objects.filter(dental_record=dental_record).prefetch_related('surfaces').order_by('tooth_number')
        
        # Build chart_data for JavaScript
        chart_data = {}
        for t in teeth:
            chart_data[str(t.tooth_number)] = {
                'id': t.id,
                'condition': t.condition,
                'notes': t.notes or '',
                'tooth_type': t.tooth_type,
            }
        
        response = render(request, 'dental_records/partials/dental_chart_htmx_response.html', {
            'dental_record': dental_record,
            'teeth': teeth,
            'chart_data': json.dumps(chart_data),
            'message': f'Tooth #{tooth_number} deleted successfully.',
        })
        # Add HX-Trigger header to show message and update chart
        response['HX-Trigger'] = json.dumps({
            'showToothMessage': f'Tooth #{tooth_number} deleted successfully.',
            'updateChartData': chart_data
        })
        return response
    
    return JsonResponse({
        'success': True,
        'message': f'Tooth #{tooth_number} deleted successfully.'
    })


@login_required
@role_required('admin', 'staff', 'doctor')
def dental_chart_api_update_surface(request, record_id, tooth_id):
    """Update surface condition for a specific tooth"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
    
    dental_record = get_object_or_404(DentalRecord, pk=record_id)
    tooth = get_object_or_404(DentalChart, pk=tooth_id, dental_record=dental_record)
    
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)
    
    surface_name = data.get('surface')
    condition = data.get('condition', 'healthy')
    notes = data.get('notes', '')
    
    if not surface_name:
        return JsonResponse({'success': False, 'error': 'Surface name is required'}, status=400)
    
    valid_surfaces = ['mesial', 'distal', 'buccal', 'lingual', 'occlusal', 'incisal']
    if surface_name not in valid_surfaces:
        return JsonResponse({'success': False, 'error': f'Invalid surface. Must be one of: {", ".join(valid_surfaces)}'}, status=400)
    
    # Create or update the surface
    surface, created = ToothSurface.objects.update_or_create(
        tooth=tooth,
        surface=surface_name,
        defaults={
            'condition': condition,
            'notes': notes,
        }
    )
    
    return JsonResponse({
        'success': True,
        'created': created,
        'surface': {
            'id': surface.id,
            'surface': surface.surface,
            'condition': surface.condition,
            'notes': surface.notes,
        }
    })


@login_required
@role_required('admin', 'staff', 'doctor')
def dental_chart_api_delete_surface(request, record_id, tooth_id, surface_id):
    """Delete a surface marking from a tooth"""
    if request.method != 'DELETE':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
    
    dental_record = get_object_or_404(DentalRecord, pk=record_id)
    tooth = get_object_or_404(DentalChart, pk=tooth_id, dental_record=dental_record)
    surface = get_object_or_404(ToothSurface, pk=surface_id, tooth=tooth)
    
    surface.delete()
    
    return JsonResponse({'success': True})


@login_required
@role_required('admin', 'staff', 'doctor')
def dental_chart_api_bulk_update(request, record_id):
    """Bulk update multiple teeth at once (for multi-select feature)"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
    
    dental_record = get_object_or_404(DentalRecord, pk=record_id)
    is_htmx = request.headers.get('HX-Request')
    
    # Parse data from either JSON or form data
    if request.content_type == 'application/json':
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            if is_htmx:
                return render(request, 'dental_records/partials/dental_chart_message.html', {
                    'message': 'Invalid JSON data',
                    'message_type': 'error'
                })
            return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)
        tooth_numbers = data.get('tooth_numbers', [])
        condition = data.get('condition', 'healthy')
        notes = data.get('notes', '')
    else:
        # Form data - tooth_numbers_json is a JSON string of selected teeth
        tooth_numbers_json = request.POST.get('tooth_numbers_json', '[]')
        try:
            tooth_numbers = json.loads(tooth_numbers_json)
        except json.JSONDecodeError:
            tooth_numbers = []
        condition = request.POST.get('condition', 'healthy')
        notes = request.POST.get('notes', '')
    
    if not tooth_numbers:
        if is_htmx:
            return render(request, 'dental_records/partials/dental_chart_message.html', {
                'message': 'No teeth selected',
                'message_type': 'error'
            })
        return JsonResponse({'success': False, 'error': 'No teeth selected'}, status=400)
    
    updated_teeth = []
    errors = []
    
    for tooth_number in tooth_numbers:
        try:
            tooth_number = int(tooth_number)
            quadrant = tooth_number // 10
            position = tooth_number % 10
            
            # Determine tooth type
            if quadrant in [1, 2, 3, 4]:
                if position < 1 or position > 8:
                    errors.append(f'Invalid position for tooth {tooth_number}')
                    continue
                tooth_type = 'permanent'
            elif quadrant in [5, 6, 7, 8]:
                if position < 1 or position > 5:
                    errors.append(f'Invalid position for tooth {tooth_number}')
                    continue
                tooth_type = 'primary'
            else:
                errors.append(f'Invalid quadrant for tooth {tooth_number}')
                continue
            
            tooth, _ = DentalChart.objects.update_or_create(
                dental_record=dental_record,
                tooth_number=tooth_number,
                defaults={
                    'tooth_type': tooth_type,
                    'condition': condition,
                    'notes': notes,
                }
            )
            updated_teeth.append(tooth_number)
        except (ValueError, TypeError):
            errors.append(f'Invalid tooth number: {tooth_number}')
    
    if is_htmx:
        # Return HTMX response with updated teeth table and chart data
        teeth = DentalChart.objects.filter(dental_record=dental_record).order_by('tooth_number')
        
        # Build chart_data for JavaScript
        chart_data = {}
        for tooth in teeth:
            chart_data[str(tooth.tooth_number)] = {
                'id': tooth.id,
                'condition': tooth.condition,
                'notes': tooth.notes or '',
                'tooth_type': tooth.tooth_type,
            }
        
        response = render(request, 'dental_records/partials/dental_chart_htmx_response.html', {
            'dental_record': dental_record,
            'teeth': teeth,
            'chart_data': json.dumps(chart_data),
            'message': f'Successfully updated {len(updated_teeth)} teeth',
        })
        # Add HX-Trigger header to close modal and show message
        response['HX-Trigger'] = json.dumps({
            'closeBulkModal': True,
            'showToothMessage': f'Successfully updated {len(updated_teeth)} teeth',
            'updateChartData': chart_data
        })
        return response
    
    return JsonResponse({
        'success': True,
        'updated_count': len(updated_teeth),
        'updated_teeth': updated_teeth,
        'errors': errors,
    })


@login_required
@role_required('admin', 'staff', 'doctor')
def dental_chart_api_save_snapshot(request, record_id):
    """Save a snapshot of the current dental chart for comparison"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
    
    dental_record = get_object_or_404(DentalRecord, pk=record_id)
    
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        data = {}
    
    notes = data.get('notes', '')
    
    # Build snapshot data
    teeth = dental_record.dental_chart.all().prefetch_related('surfaces')
    chart_data = []
    
    for tooth in teeth:
        tooth_data = {
            'tooth_number': tooth.tooth_number,
            'tooth_type': tooth.tooth_type,
            'condition': tooth.condition,
            'notes': tooth.notes,
            'surfaces': []
        }
        for surface in tooth.surfaces.all():
            tooth_data['surfaces'].append({
                'surface': surface.surface,
                'condition': surface.condition,
                'notes': surface.notes,
            })
        chart_data.append(tooth_data)
    
    # Create snapshot
    snapshot = DentalChartSnapshot.objects.create(
        dental_record=dental_record,
        notes=notes,
        chart_data=chart_data,
        created_by=request.user,
    )
    
    return JsonResponse({
        'success': True,
        'snapshot_id': snapshot.id,
        'snapshot_date': snapshot.snapshot_date.isoformat(),
    })


@login_required
@role_required('admin', 'staff', 'doctor')
def dental_chart_api_get_snapshots(request, record_id):
    """Get list of all snapshots for a dental record"""
    dental_record = get_object_or_404(DentalRecord, pk=record_id)
    
    snapshots = dental_record.chart_snapshots.all()
    
    snapshots_data = []
    for snapshot in snapshots:
        snapshots_data.append({
            'id': snapshot.id,
            'date': snapshot.snapshot_date.isoformat(),
            'notes': snapshot.notes,
            'created_by': snapshot.created_by.get_full_name() if snapshot.created_by else 'Unknown',
            'teeth_count': len(snapshot.chart_data) if snapshot.chart_data else 0,
        })
    
    return JsonResponse({'snapshots': snapshots_data})


@login_required
@role_required('admin', 'staff', 'doctor')
def dental_chart_api_get_snapshot(request, record_id, snapshot_id):
    """Get a specific snapshot's data for comparison"""
    dental_record = get_object_or_404(DentalRecord, pk=record_id)
    snapshot = get_object_or_404(DentalChartSnapshot, pk=snapshot_id, dental_record=dental_record)
    
    return JsonResponse({
        'id': snapshot.id,
        'date': snapshot.snapshot_date.isoformat(),
        'notes': snapshot.notes,
        'created_by': snapshot.created_by.get_full_name() if snapshot.created_by else 'Unknown',
        'chart_data': snapshot.chart_data,
    })


@login_required
@role_required('admin', 'staff', 'doctor')
def dental_chart_api_compare_snapshots(request, record_id):
    """Compare two snapshots to see changes over time"""
    dental_record = get_object_or_404(DentalRecord, pk=record_id)
    
    snapshot1_id = request.GET.get('snapshot1')
    snapshot2_id = request.GET.get('snapshot2')
    
    if not snapshot1_id or not snapshot2_id:
        return JsonResponse({'success': False, 'error': 'Both snapshot IDs are required'}, status=400)
    
    snapshot1 = get_object_or_404(DentalChartSnapshot, pk=snapshot1_id, dental_record=dental_record)
    snapshot2 = get_object_or_404(DentalChartSnapshot, pk=snapshot2_id, dental_record=dental_record)
    
    # Build comparison data
    teeth1 = {t['tooth_number']: t for t in snapshot1.chart_data or []}
    teeth2 = {t['tooth_number']: t for t in snapshot2.chart_data or []}
    
    all_teeth = set(teeth1.keys()) | set(teeth2.keys())
    
    changes = []
    for tooth_num in sorted(all_teeth):
        tooth1 = teeth1.get(tooth_num)
        tooth2 = teeth2.get(tooth_num)
        
        if tooth1 and tooth2:
            if tooth1['condition'] != tooth2['condition']:
                changes.append({
                    'tooth_number': tooth_num,
                    'type': 'condition_changed',
                    'from': tooth1['condition'],
                    'to': tooth2['condition'],
                })
        elif tooth1 and not tooth2:
            changes.append({
                'tooth_number': tooth_num,
                'type': 'removed',
                'condition': tooth1['condition'],
            })
        elif not tooth1 and tooth2:
            changes.append({
                'tooth_number': tooth_num,
                'type': 'added',
                'condition': tooth2['condition'],
            })
    
    return JsonResponse({
        'snapshot1': {
            'id': snapshot1.id,
            'date': snapshot1.snapshot_date.isoformat(),
        },
        'snapshot2': {
            'id': snapshot2.id,
            'date': snapshot2.snapshot_date.isoformat(),
        },
        'changes': changes,
        'total_changes': len(changes),
    })


@login_required
@role_required('admin', 'staff', 'doctor')
def dental_chart_api_export(request, record_id):
    """Export the dental chart data as JSON"""
    dental_record = get_object_or_404(DentalRecord, pk=record_id)
    
    teeth = dental_record.dental_chart.all().prefetch_related('surfaces')
    
    export_data = {
        'record_id': record_id,
        'patient_name': dental_record.patient.get_full_name(),
        'examination_date': dental_record.date_of_examination.isoformat() if dental_record.date_of_examination else None,
        'exported_at': timezone.now().isoformat(),
        'teeth': []
    }
    
    for tooth in teeth:
        tooth_data = {
            'tooth_number': tooth.tooth_number,
            'fdi_notation': f"Q{tooth.fdi_quadrant}-{tooth.fdi_tooth_position}",
            'quadrant_name': tooth.quadrant_name,
            'tooth_type': tooth.tooth_type,
            'condition': tooth.condition,
            'condition_display': tooth.get_condition_display(),
            'notes': tooth.notes,
            'surfaces': []
        }
        
        for surface in tooth.surfaces.all():
            tooth_data['surfaces'].append({
                'surface': surface.surface,
                'surface_display': surface.get_surface_display(),
                'condition': surface.condition,
                'condition_display': surface.get_condition_display(),
                'notes': surface.notes,
            })
        
        export_data['teeth'].append(tooth_data)
    
    return JsonResponse(export_data, json_dumps_params={'indent': 2})
