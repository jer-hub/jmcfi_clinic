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
    DentalServicesPerioForm,
    DentalServicesOperativeForm,
    DentalServicesSurgeryForm,
    DentalServicesProsthoForm,
    DentalServicesEndoForm,
    DentalServicesPediatricForm,
    DentalServicesDentistOtherForm,
)


# ═══════════════════════════════════════════════════════════════════════════
# Dental Services — HSS-Form0003 (dental records / examination)
# ═══════════════════════════════════════════════════════════════════════════

class DentalListView(BaseFormListView):
    model = DentalHealthForm
    template_name = 'health_forms_services/dental_services_list.html'
    detail_url_name = 'health_forms_services:dental_services_detail'
    edit_url_name = 'health_forms_services:edit_dental_services'
    create_url_name = 'health_forms_services:create_dental_services'
    form_type_label = 'Dental Services (HSS-Form0003)'
    search_fields = ['last_name', 'first_name', 'user__email', 'email_address']
    status_choices = DentalHealthForm.Status


class DentalDetailView(BaseFormDetailView):
    model = DentalHealthForm
    template_name = 'health_forms_services/dental_services_detail.html'
    list_url_name = 'health_forms_services:dental_services_list'
    edit_url_name = 'health_forms_services:edit_dental_services'
    export_url_name = 'health_forms_services:export_dental_services_docx'
    docx_export_url_name = 'health_forms_services:export_dental_services_docx'
    review_url_name = 'health_forms_services:review_dental_services'
    delete_url_name = 'health_forms_services:delete_dental_services'

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
    template_name = 'health_forms_services/edit_dental_services.html'
    detail_url_name = 'health_forms_services:dental_services_detail'
    edit_url_name = 'health_forms_services:edit_dental_services'
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
    edit_url_name = 'health_forms_services:edit_patient_chart'
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
    edit_url_name = 'health_forms_services:edit_prescription'
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
# Dental Health Forms — Dental Form 2 (services checklist)
# ═══════════════════════════════════════════════════════════════════════════

class DentalServicesListView(BaseFormListView):
    model = DentalServicesRequest
    template_name = 'health_forms_services/dental_forms_list.html'
    detail_url_name = 'health_forms_services:dental_form_detail'
    edit_url_name = 'health_forms_services:edit_dental_form'
    create_url_name = 'health_forms_services:create_dental_form'
    form_type_label = 'Dental Health Forms (Dental Form 2)'
    search_fields = ['last_name', 'first_name', 'middle_name', 'user__email']
    status_choices = DentalServicesRequest.Status


class DentalServicesDetailView(BaseFormDetailView):
    model = DentalServicesRequest
    template_name = 'health_forms_services/dental_form_detail.html'
    list_url_name = 'health_forms_services:dental_forms_list'
    edit_url_name = 'health_forms_services:edit_dental_form'
    review_url_name = 'health_forms_services:review_dental_form'
    delete_url_name = 'health_forms_services:delete_dental_form'
    docx_export_url_name = 'health_forms_services:export_dental_form_docx'

    @staticmethod
    def _bool_field(label, value, span='half'):
        return {'label': label, 'value': bool(value), 'type': 'bool', 'span': span}

    @staticmethod
    def _text_field(label, value, span='half'):
        return {'label': label, 'value': value or '—', 'type': 'text', 'span': span}

    @classmethod
    def _service_rows(cls, service_items):
        """Render only services with actionable details for cleaner UX."""
        fields = []
        for label, checked, detail in service_items:
            detail_text = (detail or '').strip() if detail is not None else ''

            # For services that have detail fields, hide rows until details exist.
            if detail is not None:
                if not detail_text:
                    continue
                fields.append(cls._text_field(label, detail_text, span='full'))
                continue

            # For simple checkbox-only items, show only when selected.
            if checked:
                fields.append(cls._text_field(label, 'Requested', span='full'))
        return fields

    @classmethod
    def _checklist_categories(cls, obj):
        """Category groupings aligned with generate_dental_services() in exports.py."""
        return [
            (
                'perio',
                'Periodontics',
                'fa-teeth',
                [
                    ('Oral prophylaxis', obj.perio_oral_prophylaxis, None),
                    ('Scaling and root planning', obj.perio_scaling_root_planning, None),
                ],
            ),
            (
                'operative',
                'Operative Dentistry',
                'fa-tooth',
                [
                    ('Class I restoration', obj.oper_class_i, obj.oper_class_i_detail),
                    ('Class II restoration', obj.oper_class_ii, obj.oper_class_ii_detail),
                    ('Class III restoration', obj.oper_class_iii, obj.oper_class_iii_detail),
                    ('Class IV restoration', obj.oper_class_iv, obj.oper_class_iv_detail),
                    ('Class V restoration', obj.oper_class_v, obj.oper_class_v_detail),
                    ('Class VI restoration', obj.oper_class_vi, obj.oper_class_vi_detail),
                    ('Onlay / Inlay', obj.oper_onlay_inlay, obj.oper_onlay_inlay_detail),
                ],
            ),
            (
                'surgery',
                'Surgery',
                'fa-syringe',
                [
                    ('Tooth extraction', obj.surg_tooth_extraction, obj.surg_tooth_extraction_detail),
                    ('Odontectomy', obj.surg_odontectomy, None),
                    ('Operculectomy', obj.surg_operculectomy, None),
                    ('Other pathological case', obj.surg_other_pathological, obj.surg_other_pathological_detail),
                ],
            ),
            (
                'prostho',
                'Prosthodontics',
                'fa-crown',
                [
                    ('Complete Denture', obj.prosth_complete_denture, None),
                    ('RPD', obj.prosth_rpd, obj.prosth_rpd_detail),
                    ('FPD', obj.prosth_fpd, obj.prosth_fpd_detail),
                    ('Single Crown', obj.prosth_single_crown, obj.prosth_single_crown_detail),
                    ('Veneers / Laminates', obj.prosth_veneers_laminates, obj.prosth_veneers_laminates_detail),
                ],
            ),
            (
                'endo',
                'Endodontics',
                'fa-wave-square',
                [
                    ('Anterior', obj.endo_anterior, obj.endo_anterior_detail),
                    ('Posterior', obj.endo_posterior, obj.endo_posterior_detail),
                ],
            ),
            (
                'pediatric',
                'Pediatric',
                'fa-child',
                [
                    ('Fluoride', obj.pedo_fluoride, None),
                    ('Sealant', obj.pedo_sealant, obj.pedo_sealant_detail),
                    ('Pulpotomy', obj.pedo_pulpotomy, obj.pedo_pulpotomy_detail),
                    ('SSC', obj.pedo_ssc, obj.pedo_ssc_detail),
                    ('Space Maintainer', obj.pedo_space_maintainer, obj.pedo_space_maintainer_detail),
                ],
            ),
        ]

    @property
    def detail_sections(self):
        obj = getattr(self, '_cached_obj', None)
        if not obj:
            return []

        info_fields = [
            {'label': 'Patient', 'value': obj.get_full_name() or '—', 'span': 'half'},
            {'label': 'Age / Gender', 'value': f"{obj.age or '—'} / {obj.get_gender_display() or '—'}", 'span': 'half'},
            {
                'label': 'Date of Birth',
                'value': obj.date_of_birth.strftime('%B %d, %Y') if obj.date_of_birth else '—',
                'type': 'date',
                'span': 'half',
            },
            {
                'label': 'Request Date',
                'value': obj.created_at.strftime('%B %d, %Y') if obj.created_at else '—',
                'type': 'date',
                'span': 'half',
            },
            {'label': 'Department', 'value': obj.department or '—', 'span': 'half'},
            {'label': 'Contact', 'value': obj.contact_number or '—', 'span': 'half'},
            {'label': 'Address', 'value': obj.address or '—', 'span': 'full'},
        ]

        sections = [
            {'key': 'info', 'label': 'Request Details', 'icon': 'fa-tooth', 'fields': info_fields},
        ]

        for key, label, icon, items in self._checklist_categories(obj):
            sections.append({
                'key': key,
                'label': label,
                'icon': icon,
                'fields': self._service_rows(items),
            })

        sections.append({
            'key': 'treatment',
            'label': 'Treatment Status',
            'icon': 'fa-notes-medical',
            'fields': [
                self._bool_field('Currently Undergoing Treatment', obj.currently_undergoing_treatment),
                self._text_field('Treatment Details', obj.currently_undergoing_treatment_detail, span='full'),
            ],
        })

        dentist_fields = [
            self._text_field('Dentist Name', obj.dentist_name),
            {
                'label': 'Date Signed',
                'value': obj.dentist_date.strftime('%B %d, %Y') if obj.dentist_date else '—',
                'type': 'date',
                'span': 'half',
            },
            self._text_field('License No.', obj.dentist_license_no),
        ]
        sections.append({
            'key': 'dentist',
            'label': 'Dentist Information',
            'icon': 'fa-user-doctor',
            'fields': dentist_fields,
        })

        return sections

    def get_object(self):
        obj = super().get_object()
        self._cached_obj = obj
        return obj


class DentalServicesEditView(BaseFormEditView):
    model = DentalServicesRequest
    template_name = 'health_forms_services/edit_dental_form.html'
    detail_url_name = 'health_forms_services:dental_form_detail'
    edit_url_name = 'health_forms_services:edit_dental_form'
    form_class_map = {
        'personal': DentalServicesPersonalInfoForm,
        'perio': DentalServicesPerioForm,
        'operative': DentalServicesOperativeForm,
        'surgery': DentalServicesSurgeryForm,
        'prostho': DentalServicesProsthoForm,
        'endo': DentalServicesEndoForm,
        'pediatric': DentalServicesPediatricForm,
        'dentist_other': DentalServicesDentistOtherForm,
    }
    tabs = [
        {'key': 'personal', 'label': 'Personal Info', 'icon': 'fa-user'},
        {'key': 'perio', 'label': 'Periodontics', 'icon': 'fa-teeth'},
        {'key': 'operative', 'label': 'Operative', 'icon': 'fa-tooth'},
        {'key': 'surgery', 'label': 'Surgery', 'icon': 'fa-syringe'},
        {'key': 'prostho', 'label': 'Prosthodontics', 'icon': 'fa-crown'},
        {'key': 'endo', 'label': 'Endodontics', 'icon': 'fa-wave-square'},
        {'key': 'pediatric', 'label': 'Pediatric', 'icon': 'fa-child'},
        {'key': 'dentist_other', 'label': 'Dentist & Other', 'icon': 'fa-user-doctor'},
    ]
    field_groups = {
        'personal': [
            {
                'label': 'Name (Last name, First name, Middle name)',
                'fields': ['last_name', 'first_name', 'middle_name'],
            },
            {
                'label': 'Address',
                'fields': ['address'],
            },
            {
                'label': '',
                'fields': ['age', 'gender', 'date_of_birth', 'contact_number', 'department'],
            },
        ],
    }
