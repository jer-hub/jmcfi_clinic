from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET, require_http_methods
from django.core.paginator import Paginator
from django.urls import reverse
from django.utils import timezone
from django.db.models import Q
from django.core.files.base import ContentFile
import hashlib
import json

from core.decorators import role_required

from .models import (
    HealthProfileForm, DentalHealthForm, DentalFormTooth, DentalFormToothSurface,
    DentalServicesRequest, PatientChart, PatientChartEntry,
    Prescription, PrescriptionItem, MedicalCertificate, DoctorSignature,
)
from .forms import (
    HealthProfilePersonalInfoForm,
    HealthProfileMedicalHistoryForm,
    HealthProfilePhysicalExamForm,
    HealthProfileDiagnosticTestsForm,
    HealthProfileClinicalSummaryForm,
    HealthFormReviewForm,
    DentalHealthPersonalInfoForm,
    DentalHealthExaminationForm,
    DentalHealthConditionsForm,
    DentalHealthFormReviewForm,
    DentalServicesPersonalInfoForm,
    DentalServicesChecklistForm,
    DentalServicesReviewForm,
    PatientChartPersonalInfoForm,
    PatientChartEntryForm,
    PatientChartReviewForm,
    PrescriptionPatientForm,
    PrescriptionItemForm,
    PrescriptionReviewForm,
    MedicalCertificateForm,
    MedicalCertificateReviewForm,
    DoctorSignatureForm,
)


@login_required
@role_required('staff', 'doctor')
def health_forms_list(request):
    """List health profile forms - filtered by user role"""
    user = request.user
    
    # Staff/Doctor can see all forms, students see only their own
    if user.role in ['staff', 'doctor', 'admin']:
        forms_qs = HealthProfileForm.objects.all()
    else:
        forms_qs = HealthProfileForm.objects.filter(user=user)
    
    # Search and filter
    search = request.GET.get('search', '')
    status_filter = request.GET.get('status', '')
    
    if search:
        forms_qs = forms_qs.filter(
            Q(last_name__icontains=search) |
            Q(first_name__icontains=search) |
            Q(user__email__icontains=search)
        )
    
    if status_filter:
        forms_qs = forms_qs.filter(status=status_filter)
    
    # Pagination
    paginator = Paginator(forms_qs, 10)
    page = request.GET.get('page', 1)
    forms_page = paginator.get_page(page)
    
    context = {
        'forms': forms_page,
        'search': search,
        'status_filter': status_filter,
        'status_choices': HealthProfileForm.Status.choices,
        'create_url': reverse('health_forms_services:manual_entry'),
    }
    
    return render(request, 'health_forms_services/forms_list.html', context)


@login_required
@role_required('staff', 'doctor')
def form_detail(request, pk):
    """View health profile form details"""
    user = request.user
    
    if user.role in ['staff', 'doctor', 'admin']:
        health_form = get_object_or_404(HealthProfileForm, pk=pk)
    else:
        health_form = get_object_or_404(HealthProfileForm, pk=pk, user=user)
    
    context = {
        'health_form': health_form,
        'can_edit': user.role in ['staff', 'doctor', 'admin'] or health_form.user == user,
        'can_review': user.role in ['staff', 'doctor', 'admin'],
    }
    
    return render(request, 'health_forms_services/form_detail.html', context)


@login_required
@role_required('staff', 'doctor')
def edit_form(request, pk):
    """Edit health profile form data"""
    user = request.user
    
    if user.role in ['staff', 'doctor', 'admin']:
        health_form = get_object_or_404(HealthProfileForm, pk=pk)
    else:
        health_form = get_object_or_404(HealthProfileForm, pk=pk, user=user)
    
    # Get all doctors for the examining_physician dropdown
    from django.contrib.auth import get_user_model
    User = get_user_model()
    doctors = User.objects.filter(role__in=['doctor', 'staff']).order_by('first_name', 'last_name')
    
    if request.method == 'POST':
        section = request.POST.get('section', 'personal')
        
        if section == 'personal':
            form = HealthProfilePersonalInfoForm(request.POST, instance=health_form)
        elif section == 'medical':
            form = HealthProfileMedicalHistoryForm(request.POST, instance=health_form)
        elif section == 'physical':
            form = HealthProfilePhysicalExamForm(request.POST, instance=health_form)
            if form.is_valid():
                # Auto-calculate BMI
                health_form = form.save(commit=False)
                health_form.calculate_bmi()
        elif section == 'diagnostic':
            form = HealthProfileDiagnosticTestsForm(request.POST, instance=health_form)
        elif section == 'clinical':
            form = HealthProfileClinicalSummaryForm(request.POST, instance=health_form)
        else:
            form = None
        
        if form and form.is_valid():
            form.save()
            messages.success(request, 'Form updated successfully.')
            return redirect('health_forms_services:form_detail', pk=pk)
    
    context = {
        'health_form': health_form,
        'doctors': doctors,
        'personal_form': HealthProfilePersonalInfoForm(instance=health_form),
        'medical_form': HealthProfileMedicalHistoryForm(instance=health_form),
        'physical_form': HealthProfilePhysicalExamForm(instance=health_form),
        'diagnostic_form': HealthProfileDiagnosticTestsForm(instance=health_form),
        'clinical_form': HealthProfileClinicalSummaryForm(instance=health_form),
    }
    
    return render(request, 'health_forms_services/edit_form.html', context)


@login_required
@require_POST
def review_form(request, pk):
    """Staff/Doctor review and approve/reject form"""
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
    """Delete a health profile form"""
    user = request.user
    
    if user.role in ['staff', 'admin']:
        health_form = get_object_or_404(HealthProfileForm, pk=pk)
    else:
        health_form = get_object_or_404(HealthProfileForm, pk=pk, user=user)
    
    # Only allow deletion of pending or rejected forms
    if health_form.status not in ['pending', 'rejected']:
        messages.error(request, 'Cannot delete a form that has been processed.')
        return redirect('health_forms_services:form_detail', pk=pk)
    
    health_form.delete()
    messages.success(request, 'Form deleted successfully.')
    
    return redirect('health_forms_services:forms_list')


@login_required
@role_required('staff', 'doctor')
def manual_entry(request):
    """Create a new health profile form — only personal info required.
    Clinical details are added from the edit page after creation."""
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

    context = {
        'personal_form': personal_form,
    }

    return render(request, 'health_forms_services/manual_entry.html', context)


@login_required
@require_GET
@role_required('staff', 'doctor')
def export_form_json(request, pk):
    """Export form data as JSON"""
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
            }
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
        }
    }
    
    return JsonResponse(data, json_dumps_params={'indent': 2})


# ========== DENTAL RECORDS FORM VIEWS (F-HSS-20-0003) ==========

@login_required
@role_required('staff', 'doctor')
def dental_forms_list(request):
    """List dental records forms"""
    user = request.user
    
    if user.role in ['staff', 'doctor', 'admin']:
        forms_qs = DentalHealthForm.objects.all()
    else:
        forms_qs = DentalHealthForm.objects.filter(user=user)
    
    # Search and filter
    search = request.GET.get('search', '')
    status_filter = request.GET.get('status', '')
    
    if search:
        forms_qs = forms_qs.filter(
            Q(last_name__icontains=search) |
            Q(first_name__icontains=search) |
            Q(user__email__icontains=search)
        )
    
    if status_filter:
        forms_qs = forms_qs.filter(status=status_filter)
    
    # Pagination
    paginator = Paginator(forms_qs, 10)
    page = request.GET.get('page', 1)
    forms_page = paginator.get_page(page)
    
    context = {
        'forms': forms_page,
        'search': search,
        'status_filter': status_filter,
        'status_choices': DentalHealthForm.Status.choices,
        'form_type': 'dental',
        'create_url': reverse('health_forms_services:create_dental_form'),
    }
    
    return render(request, 'health_forms_services/dental_forms_list.html', context)


@login_required
@role_required('staff', 'doctor')
def dental_form_detail(request, pk):
    """View dental records form details"""
    user = request.user
    
    if user.role in ['staff', 'doctor', 'admin']:
        dental_form = get_object_or_404(DentalHealthForm, pk=pk)
    else:
        dental_form = get_object_or_404(DentalHealthForm, pk=pk, user=user)
    
    teeth = dental_form.dental_chart.all().prefetch_related('surfaces')
    
    context = {
        'dental_form': dental_form,
        'teeth': teeth,
        'can_edit': user.role in ['staff', 'doctor', 'admin'] or dental_form.user == user,
        'can_review': user.role in ['staff', 'doctor', 'admin'],
    }
    
    return render(request, 'health_forms_services/dental_form_detail.html', context)


@login_required
@role_required('staff', 'doctor')
def edit_dental_form(request, pk):
    """Edit dental records form - 4 tabs: Personal, Chart, Examination, Conditions"""
    user = request.user
    
    if user.role in ['staff', 'doctor', 'admin']:
        dental_form = get_object_or_404(DentalHealthForm, pk=pk)
    else:
        dental_form = get_object_or_404(DentalHealthForm, pk=pk, user=user)
    
    if request.method == 'POST':
        section = request.POST.get('section', 'personal')
        
        if section == 'personal':
            form = DentalHealthPersonalInfoForm(request.POST, instance=dental_form)
        elif section == 'examination':
            form = DentalHealthExaminationForm(request.POST, instance=dental_form)
        elif section == 'conditions':
            form = DentalHealthConditionsForm(request.POST, instance=dental_form)
        else:
            form = None
        
        if form and form.is_valid():
            form.save()
            messages.success(request, 'Dental records form updated successfully.')
            return redirect('health_forms_services:dental_form_detail', pk=pk)
    
    context = {
        'dental_form': dental_form,
        'personal_form': DentalHealthPersonalInfoForm(instance=dental_form),
        'examination_form': DentalHealthExaminationForm(instance=dental_form),
        'conditions_form': DentalHealthConditionsForm(instance=dental_form),
    }
    
    return render(request, 'health_forms_services/edit_dental_form.html', context)


@login_required
@role_required('staff', 'doctor')
def create_dental_form(request):
    """Create a new dental records form — only personal info required.
    Clinical details are added from the edit page after creation."""
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

    context = {
        'personal_form': personal_form,
    }

    return render(request, 'health_forms_services/create_dental_form.html', context)


@login_required
@require_POST
def review_dental_form(request, pk):
    """Review and approve/reject dental form"""
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
    """Delete a dental records form"""
    user = request.user
    
    if user.role in ['staff', 'admin']:
        dental_form = get_object_or_404(DentalHealthForm, pk=pk)
    else:
        dental_form = get_object_or_404(DentalHealthForm, pk=pk, user=user)
    
    if dental_form.status not in ['pending', 'rejected']:
        messages.error(request, 'Cannot delete a form that has been processed.')
        return redirect('health_forms_services:dental_form_detail', pk=pk)
    
    dental_form.delete()
    messages.success(request, 'Dental records form deleted successfully.')
    
    return redirect('health_forms_services:dental_forms_list')


# ========== DENTAL CHART API VIEWS ==========

@login_required
@require_GET
@role_required('staff', 'doctor')
def dental_form_chart_api_get(request, pk):
    """Get all teeth data for the dental chart as JSON"""
    dental_form = get_object_or_404(DentalHealthForm, pk=pk)

    teeth = dental_form.dental_chart.all().prefetch_related('surfaces')

    teeth_data = []
    for tooth in teeth:
        surfaces_data = []
        for surface in tooth.surfaces.all():
            surfaces_data.append({
                'id': surface.id,
                'surface': surface.surface,
                'condition': surface.condition,
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
        'form_id': pk,
        'patient_name': dental_form.get_full_name(),
    })


@login_required
@require_POST
@role_required('staff', 'doctor')
def dental_form_chart_api_update(request, pk):
    """Add or update a tooth in the dental chart"""
    dental_form = get_object_or_404(DentalHealthForm, pk=pk)

    if request.content_type == 'application/json':
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)
    else:
        data = request.POST

    tooth_number = data.get('tooth_number')
    condition = data.get('condition', 'healthy')
    notes = data.get('notes', '')

    if not tooth_number:
        return JsonResponse({'success': False, 'error': 'Tooth number is required'}, status=400)

    try:
        tooth_number = int(tooth_number)
        quadrant = tooth_number // 10
        position = tooth_number % 10

        if quadrant in [1, 2, 3, 4]:
            if position < 1 or position > 8:
                return JsonResponse({'success': False, 'error': 'Invalid tooth position for permanent teeth (1-8)'}, status=400)
            tooth_type = 'permanent'
        elif quadrant in [5, 6, 7, 8]:
            if position < 1 or position > 5:
                return JsonResponse({'success': False, 'error': 'Invalid tooth position for primary teeth (1-5)'}, status=400)
            tooth_type = 'primary'
        else:
            return JsonResponse({'success': False, 'error': 'Invalid quadrant'}, status=400)
    except (ValueError, TypeError):
        return JsonResponse({'success': False, 'error': 'Invalid tooth number format'}, status=400)

    tooth, created = DentalFormTooth.objects.update_or_create(
        dental_form=dental_form,
        tooth_number=tooth_number,
        defaults={
            'tooth_type': tooth_type,
            'condition': condition,
            'notes': notes,
        }
    )

    # Handle surface conditions
    surfaces = ['mesial', 'distal', 'buccal', 'lingual', 'occlusal']
    for surface_name in surfaces:
        surface_value = data.get(f'surface_{surface_name}')
        if surface_value:
            DentalFormToothSurface.objects.update_or_create(
                tooth=tooth,
                surface=surface_name,
                defaults={'condition': surface_value}
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
        }
    })


@login_required
@require_POST
@role_required('staff', 'doctor')
def dental_form_chart_api_bulk_update(request, pk):
    """Bulk update multiple teeth at once"""
    dental_form = get_object_or_404(DentalHealthForm, pk=pk)

    if request.content_type == 'application/json':
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)
    else:
        data = request.POST
        tooth_numbers_json = data.get('tooth_numbers_json', '[]')
        try:
            data = {'tooth_numbers': json.loads(tooth_numbers_json),
                     'condition': data.get('condition', 'healthy'),
                     'notes': data.get('notes', '')}
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Invalid tooth numbers'}, status=400)

    tooth_numbers = data.get('tooth_numbers', [])
    condition = data.get('condition', 'healthy')
    notes = data.get('notes', '')

    if not tooth_numbers:
        return JsonResponse({'success': False, 'error': 'No teeth selected'}, status=400)

    updated_count = 0
    for tooth_number in tooth_numbers:
        try:
            tooth_number = int(tooth_number)
            quadrant = tooth_number // 10
            position = tooth_number % 10

            if quadrant in [1, 2, 3, 4]:
                if position < 1 or position > 8:
                    continue
                tooth_type = 'permanent'
            elif quadrant in [5, 6, 7, 8]:
                if position < 1 or position > 5:
                    continue
                tooth_type = 'primary'
            else:
                continue

            DentalFormTooth.objects.update_or_create(
                dental_form=dental_form,
                tooth_number=tooth_number,
                defaults={
                    'tooth_type': tooth_type,
                    'condition': condition,
                    'notes': notes,
                }
            )
            updated_count += 1
        except (ValueError, TypeError):
            continue

    return JsonResponse({
        'success': True,
        'updated_count': updated_count,
    })


@login_required
@require_http_methods(["DELETE", "POST"])
@role_required('staff', 'doctor')
def dental_form_chart_api_delete(request, pk, tooth_id):
    """Delete a tooth from the dental chart"""
    dental_form = get_object_or_404(DentalHealthForm, pk=pk)
    tooth = get_object_or_404(DentalFormTooth, pk=tooth_id, dental_form=dental_form)

    tooth_number = tooth.tooth_number
    tooth.delete()

    return JsonResponse({
        'success': True,
        'message': f'Tooth #{tooth_number} deleted successfully.'
    })


# ========== PATIENT CHART VIEWS (F-HSS-20-0002) ==========

@login_required
@role_required('staff', 'doctor')
def patient_chart_list(request):
    """List patient charts"""
    user = request.user

    if user.role in ['staff', 'doctor', 'admin']:
        charts_qs = PatientChart.objects.all()
    else:
        charts_qs = PatientChart.objects.filter(user=user)

    # Search and filter
    search = request.GET.get('search', '')
    status_filter = request.GET.get('status', '')

    if search:
        charts_qs = charts_qs.filter(
            Q(last_name__icontains=search) |
            Q(first_name__icontains=search) |
            Q(user__email__icontains=search)
        )

    if status_filter:
        charts_qs = charts_qs.filter(status=status_filter)

    # Pagination
    paginator = Paginator(charts_qs, 10)
    page = request.GET.get('page', 1)
    charts_page = paginator.get_page(page)

    context = {
        'charts': charts_page,
        'search': search,
        'status_filter': status_filter,
        'status_choices': PatientChart.Status.choices,
        'create_url': reverse('health_forms_services:create_patient_chart'),
    }

    return render(request, 'health_forms_services/patient_chart_list.html', context)


@login_required
@role_required('staff', 'doctor')
def patient_chart_detail(request, pk):
    """View patient chart details including consultation entries"""
    user = request.user

    if user.role in ['staff', 'doctor', 'admin']:
        chart = get_object_or_404(PatientChart, pk=pk)
    else:
        chart = get_object_or_404(PatientChart, pk=pk, user=user)

    entries = chart.entries.select_related('recorded_by').all()
    entry_form = PatientChartEntryForm()

    context = {
        'chart': chart,
        'entries': entries,
        'entry_form': entry_form,
        'can_edit': user.role in ['staff', 'doctor', 'admin'] or chart.user == user,
        'can_review': user.role in ['staff', 'doctor', 'admin'],
    }

    return render(request, 'health_forms_services/patient_chart_detail.html', context)


@login_required
@role_required('staff', 'doctor')
def edit_patient_chart(request, pk):
    """Edit patient chart personal information"""
    user = request.user

    if user.role in ['staff', 'doctor', 'admin']:
        chart = get_object_or_404(PatientChart, pk=pk)
    else:
        chart = get_object_or_404(PatientChart, pk=pk, user=user)

    if request.method == 'POST':
        form = PatientChartPersonalInfoForm(request.POST, instance=chart)
        if form.is_valid():
            form.save()
            messages.success(request, 'Patient chart updated successfully.')
            return redirect('health_forms_services:patient_chart_detail', pk=pk)
    else:
        form = PatientChartPersonalInfoForm(instance=chart)

    context = {
        'chart': chart,
        'personal_form': form,
    }

    return render(request, 'health_forms_services/edit_patient_chart.html', context)


@login_required
@role_required('staff', 'doctor')
def create_patient_chart(request):
    """Create a new patient chart"""
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

    context = {
        'personal_form': form,
    }

    return render(request, 'health_forms_services/create_patient_chart.html', context)


@login_required
@require_POST
def review_patient_chart(request, pk):
    """Review and approve/reject patient chart"""
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
    """Delete a patient chart"""
    user = request.user

    if user.role in ['staff', 'admin']:
        chart = get_object_or_404(PatientChart, pk=pk)
    else:
        chart = get_object_or_404(PatientChart, pk=pk, user=user)

    if chart.status not in ['pending', 'rejected']:
        messages.error(request, 'Cannot delete a chart that has been processed.')
        return redirect('health_forms_services:patient_chart_detail', pk=pk)

    chart.delete()
    messages.success(request, 'Patient chart deleted successfully.')

    return redirect('health_forms_services:patient_chart_list')


# ========== PATIENT CHART ENTRY API ==========

@login_required
@require_POST
@role_required('staff', 'doctor')
def add_chart_entry(request, pk):
    """Add a consultation entry to a patient chart (AJAX)"""
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
            }
        })

    return JsonResponse({'success': False, 'errors': form.errors}, status=400)


@login_required
@require_POST
@role_required('staff', 'doctor')
def delete_chart_entry(request, pk, entry_id):
    """Delete a consultation entry from a patient chart (AJAX)"""
    chart = get_object_or_404(PatientChart, pk=pk)
    entry = get_object_or_404(PatientChartEntry, pk=entry_id, patient_chart=chart)

    entry.delete()
    return JsonResponse({'success': True})


# ========== DENTAL SERVICES REQUEST VIEWS (DENTAL FORM 2) ==========

@login_required
@role_required('staff', 'doctor')
def dental_services_list(request):
    """List dental services request forms"""
    user = request.user

    if user.role in ['staff', 'doctor', 'admin']:
        forms_qs = DentalServicesRequest.objects.all()
    else:
        forms_qs = DentalServicesRequest.objects.filter(user=user)

    # Search and filter
    search = request.GET.get('search', '')
    status_filter = request.GET.get('status', '')

    if search:
        forms_qs = forms_qs.filter(
            Q(last_name__icontains=search) |
            Q(first_name__icontains=search) |
            Q(user__email__icontains=search)
        )

    if status_filter:
        forms_qs = forms_qs.filter(status=status_filter)

    # Pagination
    paginator = Paginator(forms_qs, 10)
    page = request.GET.get('page', 1)
    forms_page = paginator.get_page(page)

    context = {
        'forms': forms_page,
        'search': search,
        'status_filter': status_filter,
        'status_choices': DentalServicesRequest.Status.choices,
        'create_url': reverse('health_forms_services:create_dental_services'),
    }

    return render(request, 'health_forms_services/dental_services_list.html', context)


@login_required
@role_required('staff', 'doctor')
def dental_services_detail(request, pk):
    """View dental services request details"""
    user = request.user

    if user.role in ['staff', 'doctor', 'admin']:
        service_form = get_object_or_404(DentalServicesRequest, pk=pk)
    else:
        service_form = get_object_or_404(DentalServicesRequest, pk=pk, user=user)

    context = {
        'service_form': service_form,
        'can_edit': user.role in ['staff', 'doctor', 'admin'] or service_form.user == user,
        'can_review': user.role in ['staff', 'doctor', 'admin'],
    }

    return render(request, 'health_forms_services/dental_services_detail.html', context)


@login_required
@role_required('staff', 'doctor')
def edit_dental_services(request, pk):
    """Edit dental services request — 2 tabs: Personal Info, Services Checklist"""
    user = request.user

    if user.role in ['staff', 'doctor', 'admin']:
        service_form = get_object_or_404(DentalServicesRequest, pk=pk)
    else:
        service_form = get_object_or_404(DentalServicesRequest, pk=pk, user=user)

    if request.method == 'POST':
        section = request.POST.get('section', 'personal')

        if section == 'personal':
            form = DentalServicesPersonalInfoForm(request.POST, instance=service_form)
        elif section == 'services':
            form = DentalServicesChecklistForm(request.POST, instance=service_form)
        else:
            form = None

        if form and form.is_valid():
            form.save()
            messages.success(request, 'Dental services request updated successfully.')
            return redirect('health_forms_services:dental_services_detail', pk=pk)

    context = {
        'service_form': service_form,
        'personal_form': DentalServicesPersonalInfoForm(instance=service_form),
        'checklist_form': DentalServicesChecklistForm(instance=service_form),
    }

    return render(request, 'health_forms_services/edit_dental_services.html', context)


@login_required
@role_required('staff', 'doctor')
def create_dental_services(request):
    """Create a new dental services request — personal info first"""
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

    context = {
        'personal_form': personal_form,
    }

    return render(request, 'health_forms_services/create_dental_services.html', context)


@login_required
@require_POST
def review_dental_services(request, pk):
    """Review and approve/reject dental services request"""
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
    """Delete a dental services request"""
    user = request.user

    if user.role in ['staff', 'admin']:
        service_form = get_object_or_404(DentalServicesRequest, pk=pk)
    else:
        service_form = get_object_or_404(DentalServicesRequest, pk=pk, user=user)

    if service_form.status not in ['pending', 'rejected']:
        messages.error(request, 'Cannot delete a form that has been processed.')
        return redirect('health_forms_services:dental_services_detail', pk=pk)

    service_form.delete()
    messages.success(request, 'Dental services request deleted successfully.')

    return redirect('health_forms_services:dental_services_list')


# ========== PRESCRIPTION VIEWS (F-HSS-20-0004) ==========

@login_required
@role_required('staff', 'doctor')
def prescription_list(request):
    """List prescriptions"""
    user = request.user

    if user.role in ['staff', 'doctor', 'admin']:
        forms_qs = Prescription.objects.all()
    else:
        forms_qs = Prescription.objects.filter(user=user)

    search = request.GET.get('search', '')
    status_filter = request.GET.get('status', '')

    if search:
        forms_qs = forms_qs.filter(
            Q(patient_name__icontains=search) |
            Q(user__email__icontains=search) |
            Q(physician_name__icontains=search)
        )

    if status_filter:
        forms_qs = forms_qs.filter(status=status_filter)

    paginator = Paginator(forms_qs, 10)
    page = request.GET.get('page', 1)
    forms_page = paginator.get_page(page)

    context = {
        'forms': forms_page,
        'search': search,
        'status_filter': status_filter,
        'status_choices': Prescription.Status.choices,
        'create_url': reverse('health_forms_services:create_prescription'),
    }

    return render(request, 'health_forms_services/prescription_list.html', context)


@login_required
@role_required('staff', 'doctor')
def prescription_detail(request, pk):
    """View prescription details including medication items"""
    user = request.user

    if user.role in ['staff', 'doctor', 'admin']:
        prescription = get_object_or_404(Prescription, pk=pk)
    else:
        prescription = get_object_or_404(Prescription, pk=pk, user=user)

    items = prescription.items.all()
    item_form = PrescriptionItemForm()

    context = {
        'prescription': prescription,
        'items': items,
        'item_form': item_form,
        'can_edit': user.role in ['staff', 'doctor', 'admin'] or prescription.user == user,
        'can_review': user.role in ['staff', 'doctor', 'admin'],
    }

    return render(request, 'health_forms_services/prescription_detail.html', context)


@login_required
@role_required('staff', 'doctor')
def edit_prescription(request, pk):
    """Edit a prescription"""
    user = request.user

    if user.role in ['staff', 'doctor', 'admin']:
        prescription = get_object_or_404(Prescription, pk=pk)
    else:
        prescription = get_object_or_404(Prescription, pk=pk, user=user)

    if request.method == 'POST':
        form = PrescriptionPatientForm(request.POST, instance=prescription)
        if form.is_valid():
            form.save()
            messages.success(request, 'Prescription updated successfully.')
            return redirect('health_forms_services:prescription_detail', pk=pk)
    else:
        form = PrescriptionPatientForm(instance=prescription)

    context = {
        'prescription': prescription,
        'form': form,
    }

    return render(request, 'health_forms_services/edit_prescription.html', context)


@login_required
@role_required('staff', 'doctor')
def create_prescription(request):
    """Create a new prescription"""
    if request.method == 'POST':
        form = PrescriptionPatientForm(request.POST)
        if form.is_valid():
            prescription = form.save(commit=False)
            prescription.user = request.user
            prescription.status = Prescription.Status.PENDING
            prescription.save()

            messages.success(request, 'Prescription created. You can now add medication items.')
            return redirect('health_forms_services:prescription_detail', pk=prescription.pk)
    else:
        form = PrescriptionPatientForm()

    context = {
        'form': form,
    }

    return render(request, 'health_forms_services/create_prescription.html', context)


@login_required
@require_POST
def review_prescription(request, pk):
    """Review and approve/reject prescription"""
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
    """Delete a prescription"""
    user = request.user

    if user.role in ['staff', 'admin']:
        prescription = get_object_or_404(Prescription, pk=pk)
    else:
        prescription = get_object_or_404(Prescription, pk=pk, user=user)

    if prescription.status not in ['pending', 'rejected']:
        messages.error(request, 'Cannot delete a prescription that has been processed.')
        return redirect('health_forms_services:prescription_detail', pk=pk)

    prescription.delete()
    messages.success(request, 'Prescription deleted successfully.')

    return redirect('health_forms_services:prescription_list')


# ========== PRESCRIPTION ITEM API ==========

@login_required
@require_POST
@role_required('staff', 'doctor')
def add_prescription_item(request, pk):
    """Add a medication item to a prescription (AJAX)"""
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
            }
        })

    return JsonResponse({'success': False, 'errors': form.errors}, status=400)


@login_required
@require_POST
@role_required('staff', 'doctor')
def delete_prescription_item(request, pk, item_id):
    """Delete a medication item from a prescription (AJAX)"""
    prescription = get_object_or_404(Prescription, pk=pk)
    item = get_object_or_404(PrescriptionItem, pk=item_id, prescription=prescription)

    item.delete()
    return JsonResponse({'success': True})


# ========== MEDICAL CERTIFICATE VIEWS (F-HSS-20-0005) ==========

def _apply_medical_certificate_signature(certificate, signing_user):
    """Capture immutable signature snapshot when a certificate is completed."""
    if (
        certificate.signature_snapshot
        and certificate.signature_hash
        and certificate.signed_by_id
        and certificate.signed_at
    ):
        return True, None

    if signing_user.role != 'doctor':
        return False, 'Only a doctor account with an active signature can mark this certificate as completed.'

    signature = DoctorSignature.objects.filter(doctor=signing_user, is_active=True).first()
    if not signature or not signature.signature_image:
        return False, 'No active doctor signature found. Please upload your signature first.'

    signature.signature_image.open('rb')
    signature_bytes = signature.signature_image.read()
    signature.signature_image.close()
    if not signature_bytes:
        return False, 'Doctor signature file is empty. Please upload a valid signature image.'

    signature_name = signature.signature_image.name.rsplit('/', 1)[-1]
    certificate.signature_snapshot.save(
        f'cert_{certificate.pk}_{signing_user.pk}_{signature_name}',
        ContentFile(signature_bytes),
        save=False,
    )
    certificate.signature_hash = hashlib.sha256(signature_bytes).hexdigest()
    certificate.signed_by = signing_user
    certificate.signed_at = timezone.now()

    if not certificate.physician_name:
        certificate.physician_name = signing_user.get_full_name() or signing_user.email

    return True, None


def _doctor_missing_active_signature(user):
    """Return True when current user is a doctor without an active signature."""
    if not user.is_authenticated or user.role != 'doctor':
        return False
    return not DoctorSignature.objects.filter(doctor=user, is_active=True).exists()


@login_required
@role_required('doctor')
def my_signature(request):
    """Doctor self-service page for managing active signature."""
    signature = DoctorSignature.objects.filter(doctor=request.user).first()

    if request.method == 'POST':
        form = DoctorSignatureForm(request.POST, request.FILES, instance=signature)
        if form.is_valid():
            signature = form.save(commit=False)
            signature.doctor = request.user
            signature.updated_by = request.user
            signature.save()
            messages.success(request, 'Your signature has been updated successfully.')
            return redirect('health_forms_services:my_signature')
    else:
        form = DoctorSignatureForm(instance=signature)

    return render(request, 'health_forms_services/my_signature.html', {
        'form': form,
        'signature': signature,
    })

@login_required
@role_required('doctor', 'admin')
def medical_certificate_list(request):
    """List medical certificates"""
    user = request.user

    if user.role in ['staff', 'doctor', 'admin']:
        forms_qs = MedicalCertificate.objects.all()
    else:
        forms_qs = MedicalCertificate.objects.filter(user=user)

    search = request.GET.get('search', '')
    status_filter = request.GET.get('status', '')

    if search:
        forms_qs = forms_qs.filter(
            Q(patient_name__icontains=search) |
            Q(user__email__icontains=search) |
            Q(physician_name__icontains=search) |
            Q(diagnosis__icontains=search)
        )

    if status_filter:
        forms_qs = forms_qs.filter(status=status_filter)

    paginator = Paginator(forms_qs, 10)
    page = request.GET.get('page', 1)
    forms_page = paginator.get_page(page)

    context = {
        'forms': forms_page,
        'search': search,
        'status_filter': status_filter,
        'status_choices': MedicalCertificate.Status.choices,
        'create_url': reverse('health_forms_services:create_medical_certificate'),
        'missing_signature_warning': _doctor_missing_active_signature(user),
    }

    return render(request, 'health_forms_services/medical_certificate_list.html', context)


@login_required
def medical_certificate_detail(request, pk):
    """View medical certificate details"""
    user = request.user

    if user.role not in ['doctor', 'admin']:
        messages.error(request, 'Access denied.')
        return redirect('core:dashboard')

    if user.role in ['doctor', 'admin']:
        certificate = get_object_or_404(MedicalCertificate, pk=pk)
    else:
        certificate = get_object_or_404(MedicalCertificate, pk=pk, user=user)

    context = {
        'certificate': certificate,
        'can_edit': user.role in ['doctor', 'admin'],
        'can_review': user.role in ['doctor', 'admin'],
        'missing_signature_warning': _doctor_missing_active_signature(user),
    }

    return render(request, 'health_forms_services/medical_certificate_detail.html', context)


@login_required
def edit_medical_certificate(request, pk):
    """Edit a medical certificate"""
    user = request.user

    # Only doctors and admins can edit medical certificates
    if user.role not in ['doctor', 'admin']:
        messages.error(request, 'You do not have permission to edit medical certificates.')
        return redirect('health_forms_services:medical_certificate_detail', pk=pk)

    certificate = get_object_or_404(MedicalCertificate, pk=pk)

    # Find any document requests linked to this certificate
    linked_doc_requests = certificate.document_requests.select_related('student').all()

    if request.method == 'POST':
        previous_status = certificate.status
        form = MedicalCertificateForm(request.POST, instance=certificate)
        review_form = MedicalCertificateReviewForm(request.POST, prefix='review', instance=certificate)
        
        if form.is_valid() and review_form.is_valid():
            certificate = form.save(commit=False)

            if review_form.has_changed():
                certificate.status = review_form.cleaned_data.get('status', certificate.status)
                certificate.review_notes = review_form.cleaned_data.get('review_notes', certificate.review_notes)
                certificate.reviewed_by = request.user
                certificate.reviewed_at = timezone.now()

            if (
                certificate.status == MedicalCertificate.Status.COMPLETED
                and previous_status != MedicalCertificate.Status.COMPLETED
            ):
                signature_ok, signature_error = _apply_medical_certificate_signature(certificate, request.user)
                if not signature_ok:
                    messages.error(request, signature_error)
                    context = {
                        'certificate': certificate,
                        'form': form,
                        'review_form': review_form,
                        'linked_doc_requests': linked_doc_requests,
                    }
                    return render(request, 'health_forms_services/edit_medical_certificate.html', context)

            certificate.save()

            if review_form.has_changed():
                messages.success(request, f'Medical certificate saved and status updated to {certificate.get_status_display()}.')
            else:
                messages.success(request, 'Medical certificate updated successfully.')

            return redirect('health_forms_services:medical_certificate_detail', pk=pk)
    else:
        form = MedicalCertificateForm(instance=certificate)
        review_form = MedicalCertificateReviewForm(prefix='review', instance=certificate)

    context = {
        'certificate': certificate,
        'form': form,
        'review_form': review_form,
        'linked_doc_requests': linked_doc_requests,
        'missing_signature_warning': _doctor_missing_active_signature(user),
    }

    return render(request, 'health_forms_services/edit_medical_certificate.html', context)


@login_required
@role_required('doctor', 'admin')
def create_medical_certificate(request):
    """Create a new medical certificate"""
    if request.method == 'POST':
        form = MedicalCertificateForm(request.POST)
        if form.is_valid():
            certificate = form.save(commit=False)
            certificate.user = request.user
            certificate.status = MedicalCertificate.Status.PENDING
            certificate.save()

            messages.success(request, 'Medical certificate created successfully.')
            return redirect('health_forms_services:medical_certificate_detail', pk=certificate.pk)
    else:
        form = MedicalCertificateForm()

    context = {
        'form': form,
    }

    return render(request, 'health_forms_services/create_medical_certificate.html', context)


@login_required
@require_POST
def review_medical_certificate(request, pk):
    """Review and approve/reject medical certificate"""
    if request.user.role not in ['doctor', 'admin']:
        messages.error(request, 'Permission denied.')
        return redirect('health_forms_services:medical_certificate_detail', pk=pk)

    certificate = get_object_or_404(MedicalCertificate, pk=pk)
    previous_status = certificate.status

    form = MedicalCertificateReviewForm(request.POST, instance=certificate)
    if form.is_valid():
        certificate = form.save(commit=False)
        certificate.reviewed_by = request.user
        certificate.reviewed_at = timezone.now()

        if (
            certificate.status == MedicalCertificate.Status.COMPLETED
            and previous_status != MedicalCertificate.Status.COMPLETED
        ):
            signature_ok, signature_error = _apply_medical_certificate_signature(certificate, request.user)
            if not signature_ok:
                messages.error(request, signature_error)
                return redirect('health_forms_services:medical_certificate_detail', pk=pk)

        certificate.save()

        messages.success(request, f'Certificate status updated to {certificate.get_status_display()}.')
    else:
        messages.error(request, 'Invalid form data.')

    return redirect('health_forms_services:medical_certificate_detail', pk=pk)


@login_required
@role_required('doctor', 'admin')
def delete_medical_certificate(request, pk):
    """Delete a medical certificate"""
    user = request.user

    if user.role in ['staff', 'admin']:
        certificate = get_object_or_404(MedicalCertificate, pk=pk)
    else:
        certificate = get_object_or_404(MedicalCertificate, pk=pk, user=user)

    if certificate.status not in ['pending', 'rejected']:
        messages.error(request, 'Cannot delete a certificate that has been processed.')
        return redirect('health_forms_services:medical_certificate_detail', pk=pk)

    certificate.delete()
    messages.success(request, 'Medical certificate deleted successfully.')

    return redirect('health_forms_services:medical_certificate_list')


# ═══════════════════════════════════════════════════════════════════
#  Document Exports (.docx)
# ═══════════════════════════════════════════════════════════════════

from .exports import (
    generate_health_profile,
    generate_patient_chart,
    generate_dental_form,
    generate_dental_services,
    doc_to_response,
)


@login_required
@role_required('staff', 'doctor')
def export_health_profile_docx(request, pk):
    """Export Health Profile Form as .docx"""
    form = get_object_or_404(HealthProfileForm, pk=pk)
    doc = generate_health_profile(form)
    filename = f"Health_Profile_{form.last_name}_{form.first_name}.docx"
    return doc_to_response(doc, filename)


@login_required
@role_required('staff', 'doctor')
def export_patient_chart_docx(request, pk):
    """Export Patient Chart as .docx"""
    chart = get_object_or_404(PatientChart, pk=pk)
    doc = generate_patient_chart(chart)
    filename = f"Patient_Chart_{chart.last_name}_{chart.first_name}.docx"
    return doc_to_response(doc, filename)


@login_required
@role_required('staff', 'doctor')
def export_dental_form_docx(request, pk):
    """Export Dental Records as .docx"""
    form = get_object_or_404(DentalHealthForm, pk=pk)
    doc = generate_dental_form(form)
    filename = f"Dental_Records_{form.last_name}_{form.first_name}.docx"
    return doc_to_response(doc, filename)


@login_required
@role_required('staff', 'doctor')
def export_dental_services_docx(request, pk):
    """Export Dental Services Request as .docx"""
    form = get_object_or_404(DentalServicesRequest, pk=pk)
    doc = generate_dental_services(form)
    filename = f"Dental_Services_{form.last_name}_{form.first_name}.docx"
    return doc_to_response(doc, filename)


@login_required
@role_required('staff', 'doctor')
def export_prescription_docx(request, pk):
    """Export Prescription as print-ready HTML that mirrors the official .docx template."""
    rx = get_object_or_404(Prescription, pk=pk)
    items = rx.items.all()
    return render(request, 'health_forms_services/prescription_print.html', {
        'prescription': rx,
        'items': items,
    })


@login_required
def export_medical_certificate_docx(request, pk):
    """Export Medical Certificate as printable HTML (mirrors the official PDF form)."""
    user = request.user

    if user.role not in ['doctor', 'admin']:
        messages.error(request, 'Access denied.')
        return redirect('core:dashboard')
    
    if user.role in ['doctor', 'admin']:
        cert = get_object_or_404(MedicalCertificate, pk=pk)
    else:
        cert = get_object_or_404(MedicalCertificate, pk=pk, user=user)
    
    # Check if certificate is completed before allowing export
    if cert.status != 'completed':
        messages.error(request, 'This certificate is not yet ready for printing. Please check back later.')
        return redirect('document_request:document_requests')
    
    # Split text into lines and pad with blank lines to fill the ruled area
    DIAG_LINES = 5
    REM_LINES = 7

    diagnosis_lines = cert.diagnosis.splitlines() if cert.diagnosis else []
    remarks_lines = cert.remarks_recommendations.splitlines() if cert.remarks_recommendations else []

    diagnosis_blanks = range(max(0, DIAG_LINES - len(diagnosis_lines)))
    remarks_blanks = range(max(0, REM_LINES - len(remarks_lines)))

    return render(request, 'health_forms_services/medical_certificate_print.html', {
        'certificate': cert,
        'diagnosis_lines': diagnosis_lines,
        'diagnosis_blanks': diagnosis_blanks,
        'remarks_lines': remarks_lines,
        'remarks_blanks': remarks_blanks,
    })

