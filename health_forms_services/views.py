from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET
from django.core.paginator import Paginator
from django.utils import timezone
from django.db.models import Q

from .models import HealthProfileForm
from .forms import (
    HealthProfilePersonalInfoForm,
    HealthProfileMedicalHistoryForm,
    HealthProfilePhysicalExamForm,
    HealthProfileDiagnosticTestsForm,
    HealthProfileClinicalSummaryForm,
    HealthFormReviewForm,
)


@login_required
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
    }
    
    return render(request, 'health_forms_services/forms_list.html', context)


@login_required
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
@require_POST
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
def manual_entry(request):
    """Create a new health profile form via manual data entry"""
    if request.method == 'POST':
        personal_form = HealthProfilePersonalInfoForm(request.POST)
        medical_form = HealthProfileMedicalHistoryForm(request.POST)
        physical_form = HealthProfilePhysicalExamForm(request.POST)
        diagnostic_form = HealthProfileDiagnosticTestsForm(request.POST)
        clinical_form = HealthProfileClinicalSummaryForm(request.POST)
        
        if all([personal_form.is_valid(), medical_form.is_valid(), 
                physical_form.is_valid(), diagnostic_form.is_valid(), clinical_form.is_valid()]):
            
            # Create the health form
            health_form = HealthProfileForm(user=request.user)
            
            # Apply all form data
            for form in [personal_form, medical_form, physical_form, diagnostic_form, clinical_form]:
                for field in form.cleaned_data:
                    setattr(health_form, field, form.cleaned_data[field])
            
            # Calculate BMI
            health_form.calculate_bmi()
            health_form.status = HealthProfileForm.Status.PENDING
            health_form.save()
            
            messages.success(request, 'Health profile form created successfully.')
            return redirect('health_forms_services:form_detail', pk=health_form.pk)
    else:
        personal_form = HealthProfilePersonalInfoForm()
        medical_form = HealthProfileMedicalHistoryForm()
        physical_form = HealthProfilePhysicalExamForm()
        diagnostic_form = HealthProfileDiagnosticTestsForm()
        clinical_form = HealthProfileClinicalSummaryForm()
    
    context = {
        'personal_form': personal_form,
        'medical_form': medical_form,
        'physical_form': physical_form,
        'diagnostic_form': diagnostic_form,
        'clinical_form': clinical_form,
    }
    
    return render(request, 'health_forms_services/manual_entry.html', context)


@login_required
@require_GET
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
