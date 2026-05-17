"""
CBVs for Dental, Patient Chart, Prescription, Dental Services.
"""

from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from .base import BaseFormListView, BaseFormDetailView, BaseFormEditView
from ..models import DentalHealthForm, PatientChart, Prescription, DentalServicesRequest
from ..forms import (
    DentalHealthPersonalInfoForm,
    DentalHealthExaminationForm,
    DentalHealthConditionsForm,
    PatientChartPersonalInfoForm,
    PrescriptionPatientForm,
    DentalServicesPersonalInfoForm,
)


# ═══════════════════════════════════════════════════════════════════════════
# Dental Health Forms (F-HSS-20-0003)
# ═══════════════════════════════════════════════════════════════════════════

class DentalListView(BaseFormListView):
    model = DentalHealthForm
    template_name = 'health_forms_services/dental_forms_list.html'
    detail_url_name = 'health_forms_services:dental_form_detail'
    edit_url_name = 'health_forms_services:edit_dental_form'
    create_url_name = 'health_forms_services:create_dental_form'
    form_type_label = 'Dental Records Forms'
    search_fields = ['last_name', 'first_name', 'user__email', 'email_address']
    status_choices = DentalHealthForm.Status


class DentalDetailView(BaseFormDetailView):
    model = DentalHealthForm
    template_name = 'health_forms_services/dental_form_detail.html'
    list_url_name = 'health_forms_services:dental_forms_list'
    edit_url_name = 'health_forms_services:edit_dental_form'
    export_url_name = 'health_forms_services:export_dental_form_docx'
    docx_export_url_name = 'health_forms_services:export_dental_form_docx'
    review_url_name = 'health_forms_services:review_dental_form'
    delete_url_name = 'health_forms_services:delete_dental_form'

    @property
    def detail_sections(self):
        obj = getattr(self, '_cached_obj', None)
        if not obj:
            return []

        personal_fields = [
            {'label': 'Full Name', 'value': obj.get_full_name(), 'span': 'half'},
            {'label': 'Age / Gender', 'value': f"{obj.age or '—'} / {obj.get_gender_display() or '—'}", 'span': 'half'},
            {'label': 'Civil Status', 'value': obj.get_civil_status_display() or '—', 'span': 'half'},
            {'label': 'Date of Birth', 'value': obj.date_of_birth.strftime('%B %d, %Y') if obj.date_of_birth else '—', 'type': 'date', 'span': 'half'},
            {'label': 'Email', 'value': obj.email_address or obj.user.email or '—', 'span': 'half'},
            {'label': 'Contact', 'value': obj.contact_number or '—', 'span': 'half'},
            {'label': 'Address', 'value': obj.address or '—', 'span': 'full'},
            {'label': 'Designation', 'value': obj.get_designation_display() or '—', 'span': 'half'},
            {'label': 'Department', 'value': obj.department_college_office or '—', 'span': 'half'},
        ]

        oral_fields = [
            {'label': 'Presence of Debris', 'value': obj.presence_of_debris, 'type': 'bool', 'span': 'half'},
            {'label': 'Gingival Inflammation', 'value': obj.inflammation_of_gingiva, 'type': 'bool', 'span': 'half'},
            {'label': 'Presence of Calculus', 'value': obj.presence_of_calculus, 'type': 'bool', 'span': 'half'},
            {'label': 'Orthodontic Treatment', 'value': obj.under_orthodontic_treatment, 'type': 'bool', 'span': 'half'},
            {'label': 'Teeth Present', 'value': obj.teeth_present or '—', 'span': 'half'},
            {'label': 'Caries-Free Teeth', 'value': obj.caries_free_teeth or '—', 'span': 'half'},
            {'label': 'Decayed Teeth', 'value': obj.decayed_teeth or '—', 'span': 'half'},
            {'label': 'Missing Teeth', 'value': obj.missing_teeth or '—', 'span': 'half'},
            {'label': 'Filled Teeth', 'value': obj.filled_teeth or '—', 'span': 'half'},
        ]

        cond_fields = [
            {'label': 'Caries Free', 'value': obj.cond_caries_free, 'type': 'bool', 'span': 'half'},
            {'label': 'Poor Oral Hygiene', 'value': obj.cond_poor_oral_hygiene, 'type': 'bool', 'span': 'half'},
            {'label': 'Indicated Restoration', 'value': obj.cond_indicated_restoration, 'type': 'bool', 'span': 'half'},
            {'label': 'Indicated Extraction', 'value': obj.cond_indicated_extraction, 'type': 'bool', 'span': 'half'},
            {'label': 'Needs Prophylaxis', 'value': obj.cond_needs_oral_prophylaxis, 'type': 'bool', 'span': 'half'},
            {'label': 'No Treatment Needed', 'value': obj.cond_no_treatment_needed, 'type': 'bool', 'span': 'half'},
        ]

        return [
            {'key': 'personal', 'label': 'Personal Information', 'icon': 'fa-user', 'fields': personal_fields},
            {'key': 'oral-health', 'label': 'Oral Health & Tooth Count', 'icon': 'fa-tooth', 'fields': oral_fields},
            {'key': 'conditions', 'label': 'Conditions & Recommendations', 'icon': 'fa-clipboard-check', 'fields': cond_fields},
        ]

    def get_object(self):
        obj = super().get_object()
        self._cached_obj = obj
        return obj


class DentalEditView(BaseFormEditView):
    model = DentalHealthForm
    template_name = 'health_forms_services/edit_dental_form.html'
    detail_url_name = 'health_forms_services:dental_form_detail'
    form_class_map = {
        'personal': DentalHealthPersonalInfoForm,
        'examination': DentalHealthExaminationForm,
        'conditions': DentalHealthConditionsForm,
    }
    tabs = [
        {'key': 'personal', 'label': 'Personal Info', 'icon': 'fa-user'},
        {'key': 'examination', 'label': 'Examination', 'icon': 'fa-stethoscope'},
        {'key': 'conditions', 'label': 'Conditions', 'icon': 'fa-clipboard-check'},
    ]
    field_groups = {
        'personal': [
            {'label': 'Name', 'fields': ['last_name', 'first_name', 'middle_name']},
            {'label': 'Demographics', 'fields': ['date_of_birth', 'place_of_birth', 'age', 'gender', 'civil_status']},
            {'label': 'Contact', 'fields': ['email_address', 'contact_number', 'telephone_number', 'address']},
            {'label': 'Institution', 'fields': ['designation', 'department_college_office']},
            {'label': 'Emergency', 'fields': ['guardian_name', 'guardian_contact']},
            {'label': 'Examination Date', 'fields': ['date_of_examination']},
        ],
    }


# ═══════════════════════════════════════════════════════════════════════════
# Patient Charts (F-HSS-20-0002)
# ═══════════════════════════════════════════════════════════════════════════

class PatientChartListView(BaseFormListView):
    model = PatientChart
    template_name = 'health_forms_services/patient_chart_list.html'
    detail_url_name = 'health_forms_services:patient_chart_detail'
    edit_url_name = 'health_forms_services:edit_patient_chart'
    create_url_name = 'health_forms_services:create_patient_chart'
    form_type_label = 'Patient Charts'
    search_fields = ['last_name', 'first_name', 'user__email']
    status_choices = PatientChart.Status


class PatientChartDetailView(BaseFormDetailView):
    model = PatientChart
    template_name = 'health_forms_services/patient_chart_detail.html'
    list_url_name = 'health_forms_services:patient_chart_list'
    edit_url_name = 'health_forms_services:edit_patient_chart'
    review_url_name = 'health_forms_services:review_patient_chart'
    delete_url_name = 'health_forms_services:delete_patient_chart'

    @property
    def detail_sections(self):
        obj = getattr(self, '_cached_obj', None)
        if not obj:
            return []

        info_fields = [
            {'label': 'Full Name', 'value': obj.get_full_name(), 'span': 'half'},
            {'label': 'Age / Gender', 'value': f"{obj.age or '—'} / {obj.get_gender_display() or '—'}", 'span': 'half'},
            {'label': 'Address', 'value': obj.address or '—', 'span': 'full'},
            {'label': 'Contact', 'value': obj.contact_number or '—', 'span': 'half'},
        ]

        entry_fields = []
        for entry in obj.entries.all():
            date_str = entry.date_and_time.strftime('%b %d, %Y %H:%M') if entry.date_and_time else 'Entry'
            entry_fields.append({
                'label': date_str,
                'value': f"Findings: {entry.findings or '—'}\nOrders: {entry.doctors_orders or '—'}",
                'type': 'text',
                'span': 'full',
            })

        sections = [
            {'key': 'info', 'label': 'Patient Information', 'icon': 'fa-user', 'fields': info_fields},
        ]
        if entry_fields:
            sections.append({'key': 'entries', 'label': 'Consultation Entries', 'icon': 'fa-list', 'fields': entry_fields})
        return sections

    def get_object(self):
        obj = super().get_object()
        self._cached_obj = obj
        return obj


class PatientChartEditView(BaseFormEditView):
    model = PatientChart
    template_name = 'health_forms_services/edit_patient_chart.html'
    detail_url_name = 'health_forms_services:patient_chart_detail'
    form_class_map = {
        'personal': PatientChartPersonalInfoForm,
    }
    tabs = [
        {'key': 'personal', 'label': 'Personal Info', 'icon': 'fa-user'},
    ]


# ═══════════════════════════════════════════════════════════════════════════
# Prescriptions (F-HSS-20-0004)
# ═══════════════════════════════════════════════════════════════════════════

class PrescriptionListView(BaseFormListView):
    model = Prescription
    template_name = 'health_forms_services/prescription_list.html'
    detail_url_name = 'health_forms_services:prescription_detail'
    edit_url_name = 'health_forms_services:edit_prescription'
    create_url_name = 'health_forms_services:create_prescription'
    form_type_label = 'Prescriptions'
    search_fields = ['patient_name', 'user__email', 'physician_name']
    status_choices = Prescription.Status


class PrescriptionDetailView(BaseFormDetailView):
    model = Prescription
    template_name = 'health_forms_services/prescription_detail.html'
    list_url_name = 'health_forms_services:prescription_list'
    edit_url_name = 'health_forms_services:edit_prescription'
    review_url_name = 'health_forms_services:review_prescription'
    delete_url_name = 'health_forms_services:delete_prescription'

    @property
    def detail_sections(self):
        return []

    def get_object(self):
        qs = Prescription.objects.select_related('medical_record')
        pk = self.kwargs.get('pk')
        user = self.request.user
        from core.roles import is_patient_role
        if is_patient_role(user.role):
            obj = get_object_or_404(qs, pk=pk, user=user)
        else:
            obj = get_object_or_404(qs, pk=pk)
        self._cached_obj = obj
        return obj


class PrescriptionEditView(BaseFormEditView):
    model = Prescription
    template_name = 'health_forms_services/edit_prescription.html'
    detail_url_name = 'health_forms_services:prescription_detail'
    form_class_map = {
        'details': PrescriptionPatientForm,
    }
    tabs = [
        {'key': 'details', 'label': 'Prescription Details', 'icon': 'fa-prescription'},
    ]
    field_groups = {
        'details': [
            {'label': 'Patient Information', 'fields': ['patient_name', 'age', 'gender', 'address', 'date']},
            {'label': 'Diagnosis', 'fields': ['diagnosis']},
            {'label': 'Physician Information', 'fields': ['physician', 'physician_name', 'license_no', 'ptr_no']},
        ],
    }

    def get(self, request, *args, **kwargs):
        obj = self.get_object()
        form_instances = {}
        active_section = request.GET.get('section', (self.tabs[0]['key'] if self.tabs else 'personal'))

        for key, form_class in (self.form_class_map or {}).items():
            form_instances[key] = form_class(instance=obj)

        from ..forms import PrescriptionItemForm
        detail_url = reverse(self.detail_url_name, args=[obj.pk]) if self.detail_url_name else None
        ctx = {
            'form_obj': obj,
            'forms': form_instances,
            'tabs': self.tabs or [],
            'field_groups': self.field_groups or {},
            'active_section': active_section,
            'doctors': self.get_doctors(),
            'detail_url': detail_url,
            'prescription_items': obj.items.all(),
            'item_form': PrescriptionItemForm(),
        }
        return render(request, self.template_name, ctx)


# ═══════════════════════════════════════════════════════════════════════════
# Dental Services Request (Dental Form 2)
# ═══════════════════════════════════════════════════════════════════════════

class DentalServicesListView(BaseFormListView):
    model = DentalServicesRequest
    template_name = 'health_forms_services/dental_services_list.html'
    detail_url_name = 'health_forms_services:dental_services_detail'
    edit_url_name = 'health_forms_services:edit_dental_services'
    create_url_name = 'health_forms_services:create_dental_services'
    form_type_label = 'Dental Services Requests'
    search_fields = ['patient_name', 'user__email']
    status_choices = DentalServicesRequest.Status


class DentalServicesDetailView(BaseFormDetailView):
    model = DentalServicesRequest
    template_name = 'health_forms_services/dental_services_detail.html'
    list_url_name = 'health_forms_services:dental_services_list'
    edit_url_name = 'health_forms_services:edit_dental_services'
    review_url_name = 'health_forms_services:review_dental_services'
    delete_url_name = 'health_forms_services:delete_dental_services'

    @property
    def detail_sections(self):
        obj = getattr(self, '_cached_obj', None)
        if not obj:
            return []

        info_fields = [
            {'label': 'Patient', 'value': obj.get_full_name() or '—', 'span': 'half'},
            {'label': 'Age / Gender', 'value': f"{obj.age or '—'} / {obj.get_gender_display() or '—'}", 'span': 'half'},
            {'label': 'Date', 'value': obj.created_at.strftime('%B %d, %Y') if obj.created_at else '—', 'type': 'date', 'span': 'half'},
            {'label': 'Department', 'value': obj.department or '—', 'span': 'half'},
            {'label': 'Contact', 'value': obj.contact_number or '—', 'span': 'half'},
            {'label': 'Address', 'value': obj.address or '—', 'span': 'full'},
        ]

        service_items = []
        for svc in obj.selected_services:
            service_items.append({
                'label': svc,
                'value': 'Requested',
                'type': 'bool',
                'span': 'half',
            })

        sections = [
            {'key': 'info', 'label': 'Request Details', 'icon': 'fa-tooth', 'fields': info_fields},
        ]
        if service_items:
            sections.append({'key': 'services', 'label': 'Requested Services', 'icon': 'fa-list-check', 'fields': service_items})
        return sections

    def get_object(self):
        obj = super().get_object()
        self._cached_obj = obj
        return obj


class DentalServicesEditView(BaseFormEditView):
    model = DentalServicesRequest
    template_name = 'health_forms_services/edit_dental_services.html'
    detail_url_name = 'health_forms_services:dental_services_detail'
    form_class_map = {
        'details': DentalServicesPersonalInfoForm,
    }
    tabs = [
        {'key': 'details', 'label': 'Request Details', 'icon': 'fa-tooth'},
    ]
