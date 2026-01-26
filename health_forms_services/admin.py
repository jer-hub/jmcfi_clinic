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
        ('Medical History', {
            'fields': ('immunization_records', 'illness_history', 'allergies', 'current_medications'),
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
        ('Physical Examination', {
            'fields': (
                ('blood_pressure', 'heart_rate', 'respiratory_rate'),
                ('temperature', 'spo2'),
                ('height', 'weight', 'bmi', 'bmi_remarks'),
                'physical_exam_findings', 'other_findings'
            ),
            'classes': ('collapse',)
        }),
        ('Diagnostic Tests', {
            'fields': ('diagnostic_tests',),
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
