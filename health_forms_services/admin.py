from django.contrib import admin
from .models import HealthProfileForm


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
