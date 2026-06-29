"""
Class-based views for Health Profile Forms (F-HSS-20-0001).
"""

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect

from .base import BaseFormListView, BaseFormDetailView, BaseFormEditView
from core.models import PatientProfile, StaffProfile
from core.roles import is_patient_role
from ..models import HealthProfileForm
from ..forms import (
    HealthProfilePersonalInfoForm,
    HealthProfileMedicalHistoryForm,
    HealthProfilePhysicalExamForm,
    HealthProfileDiagnosticTestsForm,
    HealthProfileClinicalSummaryForm,
)


# ── List View ──────────────────────────────────────────────────────────────

class HealthProfileListView(BaseFormListView):
    model = HealthProfileForm
    template_name = 'health_forms_services/forms_list.html'
    detail_url_name = 'health_forms_services:form_detail'
    edit_url_name = 'health_forms_services:edit_form'
    create_url_name = 'health_forms_services:manual_entry'
    form_type_label = 'Health Profile Forms'
    bulk_action_url_name = 'health_forms_services:bulk_review'
    search_fields = ['last_name', 'first_name', 'user__email', 'email_address']
    status_choices = HealthProfileForm.Status


# ── Detail View ────────────────────────────────────────────────────────────

class HealthProfileDetailView(BaseFormDetailView):
    model = HealthProfileForm
    template_name = 'health_forms_services/form_detail.html'
    list_url_name = 'health_forms_services:forms_list'
    edit_url_name = 'health_forms_services:edit_form'
    export_url_name = 'health_forms_services:export_form'
    docx_export_url_name = 'health_forms_services:export_health_profile_docx'
    review_url_name = 'health_forms_services:review_form'
    delete_url_name = 'health_forms_services:delete_form'

    @staticmethod
    def _has_detail_value(field):
        value = field.get('value')
        field_type = field.get('type')
        if field_type == 'bool':
            return bool(value)
        if value is None:
            return False
        if isinstance(value, str):
            return bool(value.strip())
        return True

    def _with_data_only(self, fields):
        return [field for field in fields if self._has_detail_value(field)]

    @property
    def detail_sections(self):
        obj = getattr(self, '_cached_obj', None)
        if not obj:
            return []

        age_gender_parts = []
        if obj.age is not None:
            age_gender_parts.append(str(obj.age))
        if obj.get_gender_display():
            age_gender_parts.append(obj.get_gender_display())

        personal_fields = [
            {'label': 'Full Name', 'value': obj.get_full_name(), 'span': 'half'},
            {'label': 'Date of Birth', 'value': obj.date_of_birth.strftime('%B %d, %Y') if obj.date_of_birth else '', 'type': 'date', 'span': 'half'},
            {'label': 'Age / Gender', 'value': ' / '.join(age_gender_parts), 'span': 'half'},
            {'label': 'Civil Status', 'value': obj.get_civil_status_display() or '', 'span': 'half'},
            {'label': 'Place of Birth', 'value': obj.place_of_birth, 'span': 'half'},
            {'label': 'Citizenship', 'value': obj.citizenship, 'span': 'half'},
            {'label': 'Religion', 'value': obj.religion, 'span': 'half'},
            {'label': 'Email', 'value': obj.email_address or obj.user.email or '', 'span': 'half'},
            {'label': 'Mobile', 'value': obj.mobile_number, 'span': 'half'},
            {'label': 'Telephone', 'value': obj.telephone_number, 'span': 'half'},
            {'label': 'ZIP Code', 'value': obj.zip_code, 'span': 'half'},
            {'label': 'Permanent Address', 'value': obj.permanent_address, 'span': 'full'},
            {'label': 'Current Address', 'value': obj.current_address, 'span': 'full'},
            {'label': 'Designation', 'value': obj.get_designation_display() or '', 'span': 'half'},
            {'label': 'Institution ID', 'value': obj.institution_id, 'span': 'half'},
            {'label': 'Department', 'value': obj.department_college_office, 'span': 'full'},
            {'label': 'Course / Program', 'value': obj.course, 'span': 'half'},
            {'label': 'Year Level', 'value': obj.year_level, 'span': 'half'},
            {'label': 'Position', 'value': obj.position, 'span': 'half'},
            {'label': 'Specialization', 'value': obj.specialization, 'span': 'half'},
            {'label': 'License Number', 'value': obj.license_number, 'span': 'half'},
            {'label': 'PTR No.', 'value': obj.ptr_no, 'span': 'half'},
            {'label': 'Emergency Contact Name', 'value': obj.guardian_name, 'span': 'half'},
            {'label': 'Emergency Contact Number', 'value': obj.guardian_contact, 'span': 'half'},
            {'label': 'Blood Type', 'value': obj.blood_type, 'span': 'half'},
            {'label': 'Allergies', 'value': obj.allergies, 'type': 'text', 'span': 'full'},
            {'label': 'Pre-existing Medical Conditions', 'value': obj.medical_conditions, 'type': 'text', 'span': 'full'},
        ]

        vital_fields = [
            {'label': 'Blood Pressure', 'value': obj.blood_pressure, 'span': 'half'},
            {'label': 'Heart Rate', 'value': f"{obj.heart_rate} bpm" if obj.heart_rate else '', 'span': 'half'},
            {'label': 'Respiratory Rate', 'value': f"{obj.respiratory_rate} /min" if obj.respiratory_rate else '', 'span': 'half'},
            {'label': 'Temperature', 'value': f"{obj.temperature} °C" if obj.temperature else '', 'span': 'half'},
            {'label': 'SpO2', 'value': f"{obj.spo2}%" if obj.spo2 else '', 'span': 'half'},
            {'label': 'Height', 'value': f"{obj.height} m" if obj.height else '', 'span': 'half'},
            {'label': 'Weight', 'value': f"{obj.weight} kg" if obj.weight else '', 'span': 'half'},
            {'label': 'BMI', 'value': f"{obj.bmi} ({obj.bmi_remarks})" if obj.bmi else '', 'span': 'half'},
        ]

        immunization_fields = [
            {'label': 'COVID-19', 'value': obj.immunization_covid19, 'type': 'bool', 'span': 'half'},
            {'label': 'Influenza', 'value': obj.immunization_influenza, 'type': 'bool', 'span': 'half'},
            {'label': 'Hepatitis B', 'value': obj.immunization_hepatitis_b, 'type': 'bool', 'span': 'half'},
            {'label': 'MMR', 'value': obj.immunization_measles_mmr, 'type': 'bool', 'span': 'half'},
            {'label': 'DPT/Tetanus', 'value': obj.immunization_dpt_tetanus, 'type': 'bool', 'span': 'half'},
            {'label': 'Polio', 'value': obj.immunization_polio, 'type': 'bool', 'span': 'half'},
            {'label': 'Pneumonia', 'value': obj.immunization_pneumonia, 'type': 'bool', 'span': 'half'},
            {'label': 'BCG', 'value': obj.immunization_bcg, 'type': 'bool', 'span': 'half'},
        ]

        illness_fields = [
            {'label': 'Measles', 'value': obj.illness_measles, 'type': 'bool', 'span': 'half'},
            {'label': 'Mumps', 'value': obj.illness_mumps, 'type': 'bool', 'span': 'half'},
            {'label': 'Hypertension', 'value': obj.illness_hypertension, 'type': 'bool', 'span': 'half'},
            {'label': 'Diabetes', 'value': obj.illness_diabetes, 'type': 'bool', 'span': 'half'},
            {'label': 'Asthma', 'value': obj.illness_asthma, 'type': 'bool', 'span': 'half'},
            {'label': 'Chickenpox', 'value': obj.illness_chickenpox, 'type': 'bool', 'span': 'half'},
        ]

        exam_fields = [
            {'label': 'General', 'value': obj.exam_general, 'type': 'text', 'span': 'full'},
            {'label': 'HEENT', 'value': obj.exam_heent, 'type': 'text', 'span': 'full'},
            {'label': 'Chest/Lungs', 'value': obj.exam_chest_lungs, 'type': 'text', 'span': 'full'},
            {'label': 'Abdomen', 'value': obj.exam_abdomen, 'type': 'text', 'span': 'full'},
            {'label': 'Extremities', 'value': obj.exam_extremities, 'type': 'text', 'span': 'full'},
            {'label': 'Neurologic', 'value': obj.exam_neurologic, 'type': 'text', 'span': 'full'},
        ]

        clinical_fields = [
            {'label': 'Physician Impression', 'value': obj.physician_impression, 'type': 'text', 'span': 'full'},
            {'label': 'Final Remarks', 'value': obj.final_remarks, 'type': 'text', 'span': 'full'},
            {'label': 'Recommendations', 'value': obj.recommendations, 'type': 'text', 'span': 'full'},
            {'label': 'Examining Physician', 'value': obj.examining_physician.get_full_name() if obj.examining_physician else '', 'span': 'half'},
            {'label': 'Examination Date', 'value': obj.examination_date.strftime('%B %d, %Y') if obj.examination_date else '', 'type': 'date', 'span': 'half'},
        ]

        sections = [
            {'key': 'personal', 'label': 'Personal Information', 'icon': 'fa-user',
             'fields': self._with_data_only(personal_fields)},
            {'key': 'vital-signs', 'label': 'Vital Signs & Anthropometrics', 'icon': 'fa-heart-pulse',
             'fields': self._with_data_only(vital_fields)},
            {'key': 'immunizations', 'label': 'Immunization Records', 'icon': 'fa-syringe',
             'fields': self._with_data_only(immunization_fields)},
            {'key': 'illnesses', 'label': 'Illnesses & Conditions', 'icon': 'fa-notes-medical',
             'fields': self._with_data_only(illness_fields)},
            {'key': 'physical-exam', 'label': 'Physical Examination', 'icon': 'fa-stethoscope',
             'fields': self._with_data_only(exam_fields)},
            {'key': 'clinical', 'label': 'Clinical Summary', 'icon': 'fa-file-lines',
             'fields': self._with_data_only(clinical_fields)},
        ]
        return [section for section in sections if section['fields']]

    def get_object(self):
        obj = super().get_object()
        self._cached_obj = obj
        return obj


# ── Edit View ──────────────────────────────────────────────────────────────

class HealthProfileEditView(BaseFormEditView):
    model = HealthProfileForm
    template_name = 'health_forms_services/edit_form.html'
    detail_url_name = 'health_forms_services:form_detail'
    edit_url_name = 'health_forms_services:edit_form'
    personal_readonly = True
    form_class_map = {
        'personal': HealthProfilePersonalInfoForm,
        'medical': HealthProfileMedicalHistoryForm,
        'physical': HealthProfilePhysicalExamForm,
        'diagnostic': HealthProfileDiagnosticTestsForm,
        'clinical': HealthProfileClinicalSummaryForm,
    }
    tabs = [
        {'key': 'personal', 'label': 'Personal Info', 'icon': 'fa-user'},
        {'key': 'medical', 'label': 'Medical History', 'icon': 'fa-notes-medical'},
        {'key': 'physical', 'label': 'Physical Exam', 'icon': 'fa-stethoscope'},
        {'key': 'diagnostic', 'label': 'Diagnostic Tests', 'icon': 'fa-flask'},
        {'key': 'clinical', 'label': 'Clinical Summary', 'icon': 'fa-file-lines'},
    ]

    def post(self, request, *args, **kwargs):
        section = request.POST.get('section', 'personal')
        if section == 'personal':
            is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
            if is_ajax:
                return JsonResponse(
                    {'success': False, 'error': 'Personal Info section is read-only.'},
                    status=403,
                )
            messages.error(request, 'Personal Info section is read-only.')
            obj = self.get_object()
            return redirect(self.get_edit_redirect_url(obj, 'personal'))
        return super().post(request, *args, **kwargs)

    def after_section_save(self, obj, section):
        if section == 'physical':
            obj.calculate_bmi()
            return
        if section not in {'personal', 'medical'}:
            return

        user = getattr(obj, 'user', None)
        if not user:
            return

        profile_model = PatientProfile if is_patient_role(user.role) else StaffProfile
        profile, _ = profile_model.objects.get_or_create(
            user=user,
            defaults={
                'patient_id' if profile_model is PatientProfile else 'staff_id': f'TEMP_{user.id}',
            },
        )

        update_fields = []
        if section == 'personal':
            profile.blood_type = (obj.blood_type or '').strip()
            profile.allergies = (obj.allergies or '').strip()
            profile.medical_conditions = (obj.medical_conditions or '').strip()
            update_fields.extend(['blood_type', 'allergies', 'medical_conditions'])
        if section == 'medical':
            profile.allergies = (obj.allergies or '').strip()
            update_fields.append('allergies')
        if update_fields:
            profile.save(update_fields=update_fields)
