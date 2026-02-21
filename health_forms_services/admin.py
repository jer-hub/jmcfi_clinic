from django.contrib import admin
from .models import (
    HealthProfileForm, DentalHealthForm, DentalFormTooth, DentalFormToothSurface,
    DentalServicesRequest, PatientChart, PatientChartEntry,
    Prescription, PrescriptionItem, MedicalCertificate, DoctorSignature,
)


@admin.register(HealthProfileForm)
class HealthProfileFormAdmin(admin.ModelAdmin):
    list_display = ['id', 'get_name', 'user', 'status', 'designation', 'created_at', 'reviewed_at']
    list_filter = ['status', 'designation', 'gender', 'created_at']
    search_fields = ['last_name', 'first_name', 'user__email', 'email_address']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Status & Review', {
            'fields': ('user', 'status', 'reviewed_by', 'reviewed_at', 'review_notes')
        }),
        ('Personal Information', {
            'fields': (
                ('last_name', 'first_name', 'middle_name'),
                'permanent_address', 'zip_code', 'current_address',
                ('religion', 'civil_status'),
                ('place_of_birth', 'date_of_birth'),
                ('citizenship', 'age', 'gender'),
                ('email_address', 'mobile_number', 'telephone_number'),
                ('designation', 'department_college_office'),
                ('guardian_name', 'guardian_contact'),
            )
        }),
        ('Immunization Records', {
            'fields': (
                ('immunization_covid19', 'immunization_covid19_date'),
                ('immunization_influenza', 'immunization_influenza_date'),
                ('immunization_pneumonia', 'immunization_pneumonia_date'),
                ('immunization_polio', 'immunization_polio_date'),
                ('immunization_hepatitis_b', 'immunization_hepatitis_b_date'),
                ('immunization_bcg', 'immunization_bcg_date'),
                ('immunization_dpt_tetanus', 'immunization_dpt_tetanus_date'),
                ('immunization_rotavirus', 'immunization_rotavirus_date'),
                ('immunization_hib', 'immunization_hib_date'),
                ('immunization_measles_mmr', 'immunization_measles_mmr_date'),
                'immunization_others',
            ),
            'classes': ('collapse',)
        }),
        ('Illnesses/Medical Conditions', {
            'fields': (
                ('illness_measles', 'illness_mumps', 'illness_rubella'),
                ('illness_chickenpox', 'illness_ptb_pki'),
                ('illness_hypertension', 'illness_diabetes', 'illness_asthma'),
                'illness_others',
                'allergies',
                'current_medications',
            ),
            'classes': ('collapse',)
        }),
        ('OB-GYN History', {
            'fields': (
                'menarche_age', 'menstrual_duration', 'menstrual_interval',
                'menstrual_amount', 'menstrual_symptoms', 'obstetric_history'
            ),
            'classes': ('collapse',)
        }),
        ('Present Illness', {
            'fields': ('present_illness',),
            'classes': ('collapse',)
        }),
        ('Vital Signs & Anthropometrics', {
            'fields': (
                ('blood_pressure', 'heart_rate', 'respiratory_rate'),
                ('temperature', 'spo2'),
                ('height', 'weight', 'bmi', 'bmi_remarks'),
            ),
            'classes': ('collapse',)
        }),
        ('Physical Examination Findings', {
            'fields': (
                'exam_general',
                'exam_heent',
                'exam_chest_lungs',
                'exam_abdomen',
                'exam_genitourinary',
                'exam_extremities',
                'exam_neurologic',
                'exam_other_findings',
            ),
            'classes': ('collapse',)
        }),
        ('Diagnostic Tests', {
            'fields': (
                ('test_chest_xray', 'test_chest_xray_date'),
                'test_chest_xray_findings',
                ('test_cbc', 'test_cbc_date'),
                'test_cbc_findings',
                ('test_urinalysis', 'test_urinalysis_date'),
                'test_urinalysis_findings',
                ('test_drug_test', 'test_drug_test_date'),
                'test_drug_test_findings',
                ('test_psychological', 'test_psychological_date'),
                'test_psychological_findings',
                ('test_hbsag', 'test_hbsag_date'),
                'test_hbsag_findings',
                ('test_anti_hbs_titer', 'test_anti_hbs_titer_date'),
                'test_anti_hbs_titer_findings',
                ('test_fecalysis', 'test_fecalysis_date'),
                'test_fecalysis_findings',
                'test_others',
            ),
            'classes': ('collapse',)
        }),
        ('Clinical Summary', {
            'fields': (
                'physician_impression', 'final_remarks', 'recommendations',
                ('examining_physician', 'examination_date')
            ),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_name(self, obj):
        return obj.get_full_name() or '-'
    get_name.short_description = 'Name'


class DentalFormToothInline(admin.TabularInline):
    model = DentalFormTooth
    extra = 0
    fields = ['tooth_number', 'tooth_type', 'condition', 'notes']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(DentalHealthForm)
class DentalHealthFormAdmin(admin.ModelAdmin):
    list_display = ['id', 'get_name', 'user', 'status', 'designation', 'department_college_office', 'created_at']
    list_filter = ['status', 'gender', 'designation', 'created_at']
    search_fields = ['last_name', 'first_name', 'user__email', 'department_college_office']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [DentalFormToothInline]

    fieldsets = (
        ('Status & Review', {
            'fields': ('user', 'status', 'reviewed_by', 'reviewed_at', 'review_notes')
        }),
        ('Personal Information', {
            'fields': (
                ('last_name', 'first_name', 'middle_name'),
                ('age', 'gender', 'civil_status'),
                'address',
                ('date_of_birth', 'place_of_birth'),
                ('email_address', 'contact_number', 'telephone_number'),
                ('designation', 'department_college_office'),
                ('guardian_name', 'guardian_contact'),
                'date_of_examination',
            )
        }),
        ('Initial Soft Tissue Exam', {
            'fields': (
                'soft_tissue_lips', 'soft_tissue_floor_of_mouth',
                'soft_tissue_palate', 'soft_tissue_tongue', 'soft_tissue_neck_nodes',
            ),
            'classes': ('collapse',)
        }),
        ('Oral Health Condition', {
            'fields': (
                'oral_health_age_last_birthday',
                ('presence_of_debris', 'inflammation_of_gingiva', 'presence_of_calculus'),
                ('under_orthodontic_treatment',),
                'dentofacial_anomaly',
            ),
            'classes': ('collapse',)
        }),
        ('Tooth Count', {
            'fields': (
                ('teeth_present', 'caries_free_teeth'),
                ('decayed_teeth', 'missing_teeth', 'filled_teeth'),
                'total_dmf_teeth',
            ),
            'classes': ('collapse',)
        }),
        ('Initial Periodontal Exam', {
            'fields': (
                ('gingival_inflammation', 'soft_plaque_buildup', 'hard_calc_buildup'),
                ('stains', 'home_care_effectiveness', 'periodontal_condition'),
                ('periodontal_diagnosis', 'periodontitis'),
                'mucogingival_defects',
            ),
            'classes': ('collapse',)
        }),
        ('Clinical Data', {
            'fields': (
                'occlusion',
                ('tmj_pain', 'tmj_popping', 'tmj_deviation', 'tmj_tooth_wear'),
            ),
            'classes': ('collapse',)
        }),
        ('Conditions & Recommendations', {
            'fields': (
                ('cond_caries_free', 'cond_poor_oral_hygiene'),
                ('cond_indicated_restoration', 'cond_indicated_extraction'),
                ('cond_gingival_inflammation', 'cond_needs_oral_prophylaxis'),
                ('cond_needs_prosthesis', 'cond_for_endodontic'),
                ('cond_for_orthodontic', 'cond_for_sealant'),
                ('cond_others', 'cond_others_detail'),
                'cond_no_treatment_needed',
            ),
            'classes': ('collapse',)
        }),
        ('Remarks & Dentist', {
            'fields': ('remarks', 'dentist_name', 'dentist_license_no'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def get_name(self, obj):
        return obj.get_full_name() or '-'
    get_name.short_description = 'Name'


class PatientChartEntryInline(admin.TabularInline):
    model = PatientChartEntry
    extra = 1
    fields = ['date_and_time', 'findings', 'doctors_orders', 'recorded_by']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(PatientChart)
class PatientChartAdmin(admin.ModelAdmin):
    list_display = ['id', 'get_name', 'user', 'status', 'designation', 'entry_count', 'created_at']
    list_filter = ['status', 'designation', 'gender', 'created_at']
    search_fields = ['last_name', 'first_name', 'user__email', 'email_address']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [PatientChartEntryInline]
    
    fieldsets = (
        ('Status & Review', {
            'fields': ('user', 'status', 'reviewed_by', 'reviewed_at', 'review_notes')
        }),
        ('Personal Information', {
            'fields': (
                'last_name', 'first_name', 'middle_name',
                'address', 'date_of_birth', 'place_of_birth',
                'age', 'gender', 'civil_status',
                'email_address', 'contact_number', 'telephone_number',
                'designation', 'department_college_office',
            )
        }),
        ('Emergency Contact', {
            'fields': ('guardian_name', 'guardian_contact')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_name(self, obj):
        return obj.get_full_name() or '-'
    get_name.short_description = 'Name'
    
    def entry_count(self, obj):
        return obj.entries.count()
    entry_count.short_description = 'Entries'


@admin.register(PatientChartEntry)
class PatientChartEntryAdmin(admin.ModelAdmin):
    list_display = ['id', 'patient_chart', 'date_and_time', 'recorded_by', 'created_at']
    list_filter = ['date_and_time', 'created_at']
    search_fields = ['findings', 'doctors_orders', 'patient_chart__last_name', 'patient_chart__first_name']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(DentalServicesRequest)
class DentalServicesRequestAdmin(admin.ModelAdmin):
    list_display = ['id', 'get_name', 'user', 'status', 'department', 'created_at']
    list_filter = ['status', 'gender', 'created_at']
    search_fields = ['last_name', 'first_name', 'user__email', 'department']
    readonly_fields = ['created_at', 'updated_at']

    fieldsets = (
        ('Status & Review', {
            'fields': ('user', 'status', 'reviewed_by', 'reviewed_at', 'review_notes')
        }),
        ('Personal Information', {
            'fields': (
                ('last_name', 'first_name', 'middle_name'),
                'address',
                ('age', 'gender', 'date_of_birth'),
                ('contact_number', 'department'),
            )
        }),
        ('Periodontics', {
            'fields': ('perio_oral_prophylaxis', 'perio_scaling_root_planning'),
            'classes': ('collapse',)
        }),
        ('Operative Dentistry', {
            'fields': (
                ('oper_class_i', 'oper_class_i_detail'),
                ('oper_class_ii', 'oper_class_ii_detail'),
                ('oper_class_iii', 'oper_class_iii_detail'),
                ('oper_class_iv', 'oper_class_iv_detail'),
                ('oper_class_v', 'oper_class_v_detail'),
                ('oper_class_vi', 'oper_class_vi_detail'),
                ('oper_onlay_inlay', 'oper_onlay_inlay_detail'),
            ),
            'classes': ('collapse',)
        }),
        ('Surgery', {
            'fields': (
                ('surg_tooth_extraction', 'surg_tooth_extraction_detail'),
                ('surg_odontectomy', 'surg_odontectomy_detail'),
                ('surg_operculectomy', 'surg_operculectomy_detail'),
                ('surg_other_pathological', 'surg_other_pathological_detail'),
            ),
            'classes': ('collapse',)
        }),
        ('Prosthodontics', {
            'fields': (
                'prosth_complete_denture',
                ('prosth_rpd', 'prosth_rpd_detail'),
                ('prosth_fpd', 'prosth_fpd_detail'),
                ('prosth_single_crown', 'prosth_single_crown_detail'),
                ('prosth_veneers_laminates', 'prosth_veneers_laminates_detail'),
            ),
            'classes': ('collapse',)
        }),
        ('Endodontics', {
            'fields': (
                ('endo_anterior', 'endo_anterior_detail'),
                ('endo_posterior', 'endo_posterior_detail'),
            ),
            'classes': ('collapse',)
        }),
        ('Pediatric', {
            'fields': (
                'pedo_fluoride',
                ('pedo_sealant', 'pedo_sealant_detail'),
                ('pedo_pulpotomy', 'pedo_pulpotomy_detail'),
                ('pedo_ssc', 'pedo_ssc_detail'),
                ('pedo_space_maintainer', 'pedo_space_maintainer_detail'),
            ),
            'classes': ('collapse',)
        }),
        ('Other', {
            'fields': ('currently_undergoing_treatment', 'currently_undergoing_treatment_detail'),
            'classes': ('collapse',)
        }),
        ('Dentist', {
            'fields': ('dentist_name', 'dentist_date', 'dentist_license_no'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def get_name(self, obj):
        return obj.get_full_name() or '-'
    get_name.short_description = 'Name'


class PrescriptionItemInline(admin.TabularInline):
    model = PrescriptionItem
    extra = 1
    fields = ['medication_name', 'dosage', 'frequency', 'duration', 'quantity', 'instructions']


@admin.register(Prescription)
class PrescriptionAdmin(admin.ModelAdmin):
    list_display = ['id', 'patient_name', 'user', 'status', 'date', 'physician_name', 'created_at']
    list_filter = ['status', 'gender', 'created_at']
    search_fields = ['patient_name', 'user__email', 'physician_name']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [PrescriptionItemInline]

    fieldsets = (
        ('Status & Review', {
            'fields': ('user', 'status', 'reviewed_by', 'reviewed_at', 'review_notes')
        }),
        ('Patient Information', {
            'fields': (
                'patient_name',
                ('age', 'gender'),
                'address',
                'date',
            )
        }),
        ('Prescription', {
            'fields': ('prescription_body',),
        }),
        ('Physician', {
            'fields': ('physician_name', 'license_no', 'ptr_no'),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(PrescriptionItem)
class PrescriptionItemAdmin(admin.ModelAdmin):
    list_display = ['id', 'prescription', 'medication_name', 'dosage', 'frequency', 'quantity', 'created_at']
    search_fields = ['medication_name', 'prescription__patient_name']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(MedicalCertificate)
class MedicalCertificateAdmin(admin.ModelAdmin):
    list_display = ['id', 'patient_name', 'user', 'status', 'certificate_date', 'physician_name', 'signed_by', 'signed_at', 'created_at']
    list_filter = ['status', 'gender', 'created_at']
    search_fields = ['patient_name', 'user__email', 'physician_name', 'diagnosis']
    readonly_fields = ['created_at', 'updated_at', 'signed_by', 'signed_at', 'signature_hash', 'signature_snapshot']

    fieldsets = (
        ('Status & Review', {
            'fields': ('user', 'status', 'reviewed_by', 'reviewed_at', 'review_notes')
        }),
        ('Certificate Information', {
            'fields': ('certificate_date',),
        }),
        ('Patient Information', {
            'fields': (
                'patient_name',
                ('age', 'gender'),
                'address',
                'consultation_date',
            )
        }),
        ('Medical Details', {
            'fields': ('diagnosis', 'remarks_recommendations'),
        }),
        ('Physician', {
            'fields': ('physician_name', 'license_no', 'ptr_no'),
        }),
        ('Signing Snapshot', {
            'fields': ('signed_by', 'signed_at', 'signature_snapshot', 'signature_hash'),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(DoctorSignature)
class DoctorSignatureAdmin(admin.ModelAdmin):
    list_display = ['doctor', 'is_active', 'updated_by', 'updated_at']
    list_filter = ['is_active', 'updated_at']
    search_fields = ['doctor__first_name', 'doctor__last_name', 'doctor__email']
    readonly_fields = ['created_at', 'updated_at']

