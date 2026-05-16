"""Function-based views that remain after the CBV migration.

All list/detail/edit pages are now class-based (see ``forms_cbvs.py`` and
``_cbvs.py``). The functions here cover the create/review/delete/export and
HTMX/JSON API surface that the URL config still wires up.
"""

import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from core.decorators import role_required

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


# ── Helpers ────────────────────────────────────────────────────────────────


def _is_json_request(request):
    content_type = (request.content_type or '').lower()
    return content_type.startswith('application/json')


def get_form_or_404(model, pk, user, select_related_fields=None):
    """Get a form object honouring role-based access control."""
    queryset = model.objects.all()
    if select_related_fields:
        queryset = queryset.select_related(*select_related_fields)
    if user.role == 'student':
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
    if request.method == 'POST':
        personal_form = HealthProfilePersonalInfoForm(request.POST)
        if personal_form.is_valid():
            health_form = HealthProfileForm(user=request.user)
            for field in personal_form.cleaned_data:
                setattr(health_form, field, personal_form.cleaned_data[field])
            health_form.status = HealthProfileForm.Status.PENDING
            health_form.save()
            messages.success(request, 'Health profile form created. You can now fill in clinical details.')
            return redirect('health_forms_services:edit_form', pk=health_form.pk)
    else:
        personal_form = HealthProfilePersonalInfoForm()

    return render(request, 'health_forms_services/manual_entry.html', {
        'personal_form': personal_form,
    })


@login_required
@role_required('staff', 'doctor')
def load_form_section(request, pk):
    """Return a section's serialized fields for lazy-loaded edit tabs."""
    section = request.GET.get('section', 'personal')
    health_form = get_form_or_404(HealthProfileForm, pk, request.user,
                                  ['user', 'reviewed_by', 'examining_physician'])

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
        health_form.save()
        messages.success(request, f'Form status updated to {health_form.get_status_display()}.')
    else:
        messages.error(request, 'Invalid form data.')
    return redirect('health_forms_services:form_detail', pk=pk)


@login_required
@role_required('staff', 'doctor')
def delete_form(request, pk):
    user = request.user
    if user.role in ['staff', 'doctor', 'admin']:
        health_form = get_object_or_404(HealthProfileForm, pk=pk)
    else:
        health_form = get_object_or_404(HealthProfileForm, pk=pk, user=user)

    if health_form.status not in ['pending', 'rejected', 'incomplete']:
        messages.error(request, 'Cannot delete a form that has been processed.')
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
            'department': health_form.department_college_office,
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
# Dental Records Form (F-HSS-20-0003) — create, review, delete, chart API
# ═══════════════════════════════════════════════════════════════════════════


@login_required
@role_required('staff', 'doctor')
def create_dental_form(request):
    if request.method == 'POST':
        personal_form = DentalHealthPersonalInfoForm(request.POST)
        if personal_form.is_valid():
            dental_form = DentalHealthForm(user=request.user)
            for field in personal_form.cleaned_data:
                setattr(dental_form, field, personal_form.cleaned_data[field])
            dental_form.status = DentalHealthForm.Status.PENDING
            dental_form.save()
            messages.success(request, 'Dental records form created. You can now fill in clinical details.')
            return redirect('health_forms_services:edit_dental_form', pk=dental_form.pk)
    else:
        personal_form = DentalHealthPersonalInfoForm()

    return render(request, 'health_forms_services/create_dental_form.html', {
        'personal_form': personal_form,
    })


@login_required
@require_POST
def review_dental_form(request, pk):
    if request.user.role not in ['staff', 'doctor', 'admin']:
        messages.error(request, 'Permission denied.')
        return redirect('health_forms_services:dental_form_detail', pk=pk)

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
    return redirect('health_forms_services:dental_form_detail', pk=pk)


@login_required
@role_required('staff', 'doctor')
def delete_dental_form(request, pk):
    user = request.user
    if user.role in ['staff', 'doctor', 'admin']:
        dental_form = get_object_or_404(DentalHealthForm, pk=pk)
    else:
        dental_form = get_object_or_404(DentalHealthForm, pk=pk, user=user)

    if dental_form.status not in ['pending', 'rejected', 'incomplete']:
        messages.error(request, 'Cannot delete a form that has been processed.')
        return redirect('health_forms_services:dental_form_detail', pk=pk)

    dental_form.delete()
    messages.success(request, 'Dental records form deleted successfully.')
    return redirect('health_forms_services:dental_forms_list')


# ── Dental Chart API ───────────────────────────────────────────────────────


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
@role_required('staff', 'doctor')
def create_patient_chart(request):
    if request.method == 'POST':
        form = PatientChartPersonalInfoForm(request.POST)
        if form.is_valid():
            chart = PatientChart(user=request.user)
            for field in form.cleaned_data:
                setattr(chart, field, form.cleaned_data[field])
            chart.status = PatientChart.Status.PENDING
            chart.save()
            messages.success(request, 'Patient chart created successfully.')
            return redirect('health_forms_services:patient_chart_detail', pk=chart.pk)
    else:
        form = PatientChartPersonalInfoForm()

    return render(request, 'health_forms_services/create_patient_chart.html', {'personal_form': form})


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
            'entry': {
                'id': entry.id,
                'date_and_time': entry.date_and_time.strftime('%b %d, %Y %I:%M %p'),
                'findings': entry.findings,
                'doctors_orders': entry.doctors_orders,
                'recorded_by': entry.recorded_by.get_full_name() if entry.recorded_by else '',
            },
        })
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
# Dental Services Request (Dental Form 2) — create, review, delete
# ═══════════════════════════════════════════════════════════════════════════


@login_required
@role_required('staff', 'doctor')
def create_dental_services(request):
    if request.method == 'POST':
        personal_form = DentalServicesPersonalInfoForm(request.POST)
        if personal_form.is_valid():
            service_form = DentalServicesRequest(user=request.user)
            for field in personal_form.cleaned_data:
                setattr(service_form, field, personal_form.cleaned_data[field])
            service_form.status = DentalServicesRequest.Status.PENDING
            service_form.save()
            messages.success(request, 'Dental services request created. You can now fill in the services checklist.')
            return redirect('health_forms_services:edit_dental_services', pk=service_form.pk)
    else:
        personal_form = DentalServicesPersonalInfoForm()

    return render(request, 'health_forms_services/create_dental_services.html', {
        'personal_form': personal_form,
    })


@login_required
@require_POST
def review_dental_services(request, pk):
    if request.user.role not in ['staff', 'doctor', 'admin']:
        messages.error(request, 'Permission denied.')
        return redirect('health_forms_services:dental_services_detail', pk=pk)

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
    return redirect('health_forms_services:dental_services_detail', pk=pk)


@login_required
@role_required('staff', 'doctor')
def delete_dental_services(request, pk):
    user = request.user
    if user.role in ['staff', 'doctor', 'admin']:
        service_form = get_object_or_404(DentalServicesRequest, pk=pk)
    else:
        service_form = get_object_or_404(DentalServicesRequest, pk=pk, user=user)

    if service_form.status not in ['pending', 'rejected', 'incomplete']:
        messages.error(request, 'Cannot delete a form that has been processed.')
        return redirect('health_forms_services:dental_services_detail', pk=pk)

    service_form.delete()
    messages.success(request, 'Dental services request deleted successfully.')
    return redirect('health_forms_services:dental_services_list')


# ═══════════════════════════════════════════════════════════════════════════
# Prescriptions (F-HSS-20-0004) — create, review, delete, item API
# ═══════════════════════════════════════════════════════════════════════════


@login_required
@role_required('staff', 'doctor')
def create_prescription(request):
    if request.method == 'POST':
        form = PrescriptionPatientForm(request.POST)
        if form.is_valid():
            prescription = form.save(commit=False)
            prescription.user = request.user
            prescription.status = Prescription.Status.INCOMPLETE
            prescription.save()
            messages.success(request, 'Prescription created successfully.')
            return redirect('health_forms_services:prescription_detail', pk=prescription.pk)
    else:
        form = PrescriptionPatientForm()

    return render(request, 'health_forms_services/create_prescription.html', {'form': form})


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
    form = get_object_or_404(DentalHealthForm, pk=pk)
    doc = generate_dental_form(form)
    filename = f"Dental_Records_{form.last_name}_{form.first_name}.docx"
    return doc_to_response(doc, filename)


@login_required
@role_required('staff', 'doctor')
def export_dental_services_docx(request, pk):
    form = get_object_or_404(DentalServicesRequest, pk=pk)
    doc = generate_dental_services(form)
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
