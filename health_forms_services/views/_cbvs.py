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
    PATIENT_CHART_PERSONAL_SECTIONS,
    PrescriptionPatientForm,
    DentalServicesPersonalInfoForm,
    DentalServicesPerioForm,
    DentalServicesOperativeForm,
    DentalServicesSurgeryForm,
    DentalServicesProsthoForm,
    DentalServicesEndoForm,
    DentalServicesPediatricForm,
    DentalServicesDentistOtherForm,
    DENTAL_PERSONAL_INFO_SECTIONS,
    DENTAL_SOFT_TISSUE_FIELDS,
    DENTAL_ORAL_HEALTH_CHECKBOXES,
    DENTAL_TOOTH_COUNT_FIELDS,
    DENTAL_PERIODONTAL_FIELDS,
    DENTAL_TMJ_CHECKBOXES,
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
    form_type_label = 'Dental Services (HSS-Form0003)'

    @staticmethod
    def _bool_field(label, value, span='half'):
        return {'label': label, 'value': bool(value), 'type': 'bool', 'span': span}

    @staticmethod
    def _text_field(label, value, span='half'):
        return {'label': label, 'value': value or '—', 'type': 'text', 'span': span}

    @staticmethod
    def _choice_display(obj, field_name, label, span='half'):
        getter = getattr(obj, f'get_{field_name}_display', None)
        raw = getattr(obj, field_name, '')
        value = getter() if raw and getter else ''
        if not value:
            return None
        return {'label': label, 'value': value, 'span': span}

    @classmethod
    def _present_text(cls, label, value, span='half'):
        if value is None:
            return None
        text = str(value).strip()
        if not text or text == '—':
            return None
        return cls._text_field(label, text, span=span)

    @classmethod
    def _present_bool(cls, label, value):
        if not value:
            return None
        return cls._bool_field(label, True)

    @classmethod
    def _section_shell(cls, key, label, *, icon, icon_bg, icon_color, description=None, **extra):
        return {
            'key': key,
            'label': label,
            'icon': icon,
            'icon_bg': icon_bg,
            'icon_color': icon_color,
            'description': description,
            **extra,
        }

    @classmethod
    def _personal_groups(cls, obj, examined_by_name):
        from ..detail_sections import (
            BASE_PERSONAL_FIELD_LABELS,
            base_personal_value_map,
            build_personal_info_groups,
            present_text,
        )

        label_map = {
            **BASE_PERSONAL_FIELD_LABELS,
            'date_of_examination': 'Date of Examination',
        }
        value_map = base_personal_value_map(obj)
        value_map['date_of_examination'] = (
            obj.date_of_examination.strftime('%B %d, %Y') if obj.date_of_examination else ''
        )
        append_groups = []
        examined = present_text('Examined By', examined_by_name, span='full')
        if examined:
            append_groups.append({'label': 'Clinician', 'fields': [examined]})
        return build_personal_info_groups(
            obj,
            DENTAL_PERSONAL_INFO_SECTIONS,
            label_map=label_map,
            value_map=value_map,
            append_groups=append_groups,
        )

    @classmethod
    def _labeled_fields(cls, obj, field_specs, *, full_width=()):
        fields = []
        for attr, label in field_specs:
            value = getattr(obj, attr, None)
            if isinstance(value, bool):
                field = cls._present_bool(label, value)
            else:
                field = cls._present_text(label, value, span='full' if attr in full_width else 'half')
            if field:
                fields.append(field)
        return fields

    @classmethod
    def _condition_fields(cls, obj):
        items = [
            ('Caries-free', obj.cond_caries_free),
            ('Poor Oral Hygiene', obj.cond_poor_oral_hygiene),
            ('Indicated for Restoration', obj.cond_indicated_restoration),
            ('Indicated for Extraction', obj.cond_indicated_extraction),
            ('Gingival Inflammation', obj.cond_gingival_inflammation),
            ('Needs Oral Prophylaxis', obj.cond_needs_oral_prophylaxis),
            ('Needs Prosthesis', obj.cond_needs_prosthesis),
            ('For Endodontic Treatment', obj.cond_for_endodontic),
            ('For Orthodontic Treatment', obj.cond_for_orthodontic),
            ('For Sealant', obj.cond_for_sealant),
            ('No Treatment Needed', obj.cond_no_treatment_needed),
        ]
        fields = [cls._bool_field(label, checked) for label, checked in items if checked]
        if obj.cond_others and (obj.cond_others_detail or '').strip():
            fields.append(cls._text_field('Other Conditions', obj.cond_others_detail, span='full'))
        return fields

    @property
    def detail_sections(self):
        obj = getattr(self, '_cached_obj', None)
        if not obj:
            return []

        examined_by_name = ''
        if obj.examined_by_id:
            examined_by_name = obj.examined_by.get_full_name() or obj.examined_by.email

        sections = [
            self._section_shell(
                'personal',
                'Personal Information',
                icon='fa-user',
                icon_bg='bg-primary-50',
                icon_color='text-primary-600',
                description='Patient demographics, contact, and examination details.',
                groups=self._personal_groups(obj, examined_by_name),
            ),
            self._section_shell(
                'chart',
                'Dental Chart (FDI Notation)',
                icon='fa-teeth',
                icon_bg='bg-indigo-50',
                icon_color='text-indigo-600',
                description='Visual chart and list of documented teeth.',
                variant='chart',
            ),
        ]

        soft_tissue_fields = self._labeled_fields(
            obj, DENTAL_SOFT_TISSUE_FIELDS, full_width=tuple(name for name, _ in DENTAL_SOFT_TISSUE_FIELDS),
        )
        if soft_tissue_fields:
            sections.append(self._section_shell(
                'soft-tissue',
                'Initial Soft Tissue Exam',
                icon='fa-mouth',
                icon_bg='bg-rose-50',
                icon_color='text-rose-600',
                fields=soft_tissue_fields,
            ))

        oral_fields = []
        age_field = self._present_text('Age on Last Birthday', obj.oral_health_age_last_birthday)
        if age_field:
            oral_fields.append(age_field)
        for attr, label in DENTAL_ORAL_HEALTH_CHECKBOXES:
            field = self._present_bool(label, getattr(obj, attr, False))
            if field:
                oral_fields.append(field)
        anomaly = self._present_text(
            'Dentofacial Anomaly / Neoplasm / Others',
            obj.dentofacial_anomaly,
            span='full',
        )
        if anomaly:
            oral_fields.append(anomaly)
        if oral_fields:
            sections.append(self._section_shell(
                'oral-health',
                'Oral Health Condition',
                icon='fa-tooth',
                icon_bg='bg-sky-50',
                icon_color='text-sky-600',
                fields=oral_fields,
            ))

        tooth_count_fields = self._labeled_fields(obj, DENTAL_TOOTH_COUNT_FIELDS)
        if tooth_count_fields:
            sections.append(self._section_shell(
                'tooth-count',
                'Tooth Count (DMF)',
                icon='fa-hashtag',
                icon_bg='bg-violet-50',
                icon_color='text-violet-600',
                fields=tooth_count_fields,
            ))

        perio_fields = []
        for attr, label in DENTAL_PERIODONTAL_FIELDS:
            field = self._choice_display(obj, attr, label)
            if field:
                perio_fields.append(field)
        muco = self._present_text('Mucogingival Defects', obj.mucogingival_defects, span='full')
        if muco:
            perio_fields.append(muco)
        if perio_fields:
            sections.append(self._section_shell(
                'periodontal',
                'Initial Periodontal Exam',
                icon='fa-teeth',
                icon_bg='bg-emerald-50',
                icon_color='text-emerald-600',
                fields=perio_fields,
            ))

        clinical_fields = []
        occlusion = self._choice_display(obj, 'occlusion', 'Occlusion')
        if occlusion:
            clinical_fields.append(occlusion)
        for attr, label in DENTAL_TMJ_CHECKBOXES:
            field = self._present_bool(label, getattr(obj, attr, False))
            if field:
                clinical_fields.append(field)
        if clinical_fields:
            sections.append(self._section_shell(
                'clinical',
                'Clinical Data',
                icon='fa-head-side-virus',
                icon_bg='bg-amber-50',
                icon_color='text-amber-600',
                fields=clinical_fields,
            ))

        condition_fields = self._condition_fields(obj)
        if condition_fields:
            sections.append(self._section_shell(
                'conditions',
                'Conditions & Recommendations',
                icon='fa-clipboard-check',
                icon_bg='bg-primary-50',
                icon_color='text-primary-600',
                fields=condition_fields,
            ))

        dentist_fields = []
        for label, value, span in (
            ('Remarks', obj.remarks, 'full'),
            ('Dentist Name', obj.dentist_name, 'half'),
            ('License No.', obj.dentist_license_no, 'half'),
        ):
            field = self._present_text(label, value, span=span)
            if field:
                dentist_fields.append(field)
        if dentist_fields:
            sections.append(self._section_shell(
                'dentist',
                'Remarks & Dentist',
                icon='fa-user-doctor',
                icon_bg='bg-indigo-50',
                icon_color='text-indigo-600',
                fields=dentist_fields,
            ))

        return sections

    def get_object(self):
        pk = self.kwargs.get('pk')
        qs = self.model.objects.select_related('user', 'reviewed_by', 'examined_by')
        user = self.request.user
        from core.roles import is_patient_role
        if is_patient_role(user.role):
            obj = get_object_or_404(qs, pk=pk, user=user)
        else:
            obj = get_object_or_404(qs, pk=pk)
        self._cached_obj = obj
        return obj

    def get_context_data(self, obj):
        import json

        ctx = super().get_context_data(obj)
        teeth = obj.dental_chart.all().prefetch_related('surfaces')
        teeth_json = []
        for tooth in teeth:
            teeth_json.append({
                'id': tooth.id,
                'tooth_number': tooth.tooth_number,
                'tooth_type': tooth.tooth_type,
                'condition': tooth.condition,
                'notes': tooth.notes,
                'surfaces': [
                    {'id': s.id, 'surface': s.surface, 'condition': s.condition}
                    for s in tooth.surfaces.all()
                ],
            })
        ctx['dental_chart_json'] = json.dumps(teeth_json)
        ctx['dental_record'] = obj
        ctx['chart_entity_id'] = obj.pk
        return ctx


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
        {'key': 'chart', 'label': 'Dental Chart', 'icon': 'fa-teeth'},
        {'key': 'examination', 'label': 'Examination', 'icon': 'fa-stethoscope'},
        {'key': 'conditions', 'label': 'Conditions', 'icon': 'fa-clipboard-check'},
    ]

    def get_extra_edit_context(self, obj):
        return {
            'chart_api_base': reverse('health_forms_services:dental_chart_api_get', kwargs={'pk': obj.pk}),
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
    docx_export_url_name = 'health_forms_services:export_patient_chart_docx'
    form_type_label = 'Patient Chart (F-HSS-20-0002)'

    @classmethod
    def _personal_groups(cls, obj):
        from ..detail_sections import (
            BASE_PERSONAL_FIELD_LABELS,
            base_personal_value_map,
            build_personal_info_groups,
        )

        return build_personal_info_groups(
            obj,
            PATIENT_CHART_PERSONAL_SECTIONS,
            label_map=BASE_PERSONAL_FIELD_LABELS,
            value_map=base_personal_value_map(obj),
        )

    @property
    def detail_sections(self):
        obj = getattr(self, '_cached_obj', None)
        if not obj:
            return []

        return [{
            'key': 'personal',
            'label': 'Personal Information',
            'icon': 'fa-user',
            'icon_bg': 'bg-primary-50',
            'icon_color': 'text-primary-600',
            'description': 'Patient demographics and contact details.',
            'groups': self._personal_groups(obj),
        }]

    def get_object(self):
        qs = PatientChart.objects.select_related('user', 'reviewed_by').prefetch_related(
            'entries__recorded_by',
        )
        pk = self.kwargs.get('pk')
        user = self.request.user
        from core.roles import is_patient_role
        if is_patient_role(user.role):
            obj = get_object_or_404(qs, pk=pk, user=user)
        else:
            obj = get_object_or_404(qs, pk=pk)
        self._cached_obj = obj
        return obj

    def get_context_data(self, obj):
        from django.utils import timezone
        from ..forms import PatientChartEntryForm

        ctx = super().get_context_data(obj)
        ctx['chart_entries'] = list(obj.entries.all())
        ctx['entry_form'] = PatientChartEntryForm()
        ctx['entry_default_datetime'] = timezone.localtime(timezone.now()).strftime('%Y-%m-%dT%H:%M')
        ctx['can_manage_entries'] = self.request.user.role in ('staff', 'doctor', 'admin')
        ctx['add_entry_url'] = reverse('health_forms_services:add_chart_entry', kwargs={'pk': obj.pk})
        return ctx


class PatientChartEditView(BaseFormEditView):
    model = PatientChart
    template_name = 'health_forms_services/edit_patient_chart.html'
    detail_url_name = 'health_forms_services:patient_chart_detail'
    edit_url_name = 'health_forms_services:edit_patient_chart'
    edit_form_type = 'patient_chart'
    personal_readonly = False
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
        {'key': 'personal', 'label': 'Personal Info', 'short_label': 'Personal', 'icon': 'fa-user'},
        {'key': 'perio', 'label': 'Periodontics', 'short_label': 'Perio', 'icon': 'fa-teeth'},
        {'key': 'operative', 'label': 'Operative', 'icon': 'fa-tooth'},
        {'key': 'surgery', 'label': 'Surgery', 'icon': 'fa-syringe'},
        {'key': 'prostho', 'label': 'Prosthodontics', 'short_label': 'Prosth', 'icon': 'fa-crown'},
        {'key': 'endo', 'label': 'Endodontics', 'short_label': 'Endo', 'icon': 'fa-wave-square'},
        {'key': 'pediatric', 'label': 'Pediatric', 'icon': 'fa-child'},
        {'key': 'dentist_other', 'label': 'Dentist & Other', 'short_label': 'Dentist', 'icon': 'fa-user-doctor'},
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
