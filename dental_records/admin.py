from django.contrib import admin
from .models import (
    DentalRecord, DentalExamination, DentalVitalSigns,
    DentalHealthQuestionnaire, DentalSystemsReview,
    DentalHistory, PediatricDentalHistory, DentalChart
)


class DentalChartInline(admin.TabularInline):
    model = DentalChart
    extra = 0
    fields = ('tooth_number', 'tooth_type', 'condition', 'notes')


@admin.register(DentalRecord)
class DentalRecordAdmin(admin.ModelAdmin):
    list_display = ('patient', 'age', 'designation', 'date_of_examination', 'examined_by', 'consent_signed', 'created_at')
    search_fields = ('patient__username', 'patient__email', 'patient__first_name', 'patient__last_name', 'middle_name')
    list_filter = ('designation', 'gender', 'consent_signed', 'date_of_examination', 'created_at')
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'date_of_examination'
    inlines = [DentalChartInline]
    fieldsets = (
        ('Patient Information', {
            'fields': ('patient', 'middle_name', 'age', 'gender', 'civil_status', 
                      'date_of_birth', 'place_of_birth')
        }),
        ('Contact Information', {
            'fields': ('address', 'email', 'contact_number', 'telephone_number')
        }),
        ('Institutional Information', {
            'fields': ('designation', 'department_college_office')
        }),
        ('Emergency Contact', {
            'fields': ('guardian_name', 'guardian_contact')
        }),
        ('Examination Details', {
            'fields': ('date_of_examination', 'examined_by')
        }),
        ('Consent', {
            'fields': ('consent_signed', 'consent_date')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(DentalExamination)
class DentalExaminationAdmin(admin.ModelAdmin):
    list_display = ('dental_record', 'created_at')
    search_fields = ('dental_record__patient__username',)
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('Extraoral Examination', {
            'fields': ('dental_record', 'facial_symmetry', 'cutaneous_areas', 'lips', 'eyes', 'lymph_nodes', 'tmj')
        }),
        ('Intraoral Examination', {
            'fields': ('buccal_labial_mucosa', 'gingiva', 'palate_soft', 'palate_hard', 
                      'tongue', 'salivary_flow', 'oral_hygiene')
        }),
    )


@admin.register(DentalVitalSigns)
class DentalVitalSignsAdmin(admin.ModelAdmin):
    list_display = ('dental_record', 'blood_pressure', 'pulse_rate', 'temperature', 'created_at')
    search_fields = ('dental_record__patient__username',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(DentalHealthQuestionnaire)
class DentalHealthQuestionnaireAdmin(admin.ModelAdmin):
    list_display = ('dental_record', 'doctor_care_2years', 'medications_2years', 'is_pregnant', 'created_at')
    search_fields = ('dental_record__patient__username',)
    list_filter = ('doctor_care_2years', 'medications_2years', 'is_pregnant', 'created_at')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(DentalSystemsReview)
class DentalSystemsReviewAdmin(admin.ModelAdmin):
    list_display = ('dental_record', 'heart_disease', 'hypertension', 'diabetes', 'asthma', 'created_at')
    search_fields = ('dental_record__patient__username',)
    list_filter = ('heart_disease', 'hypertension', 'diabetes', 'asthma', 'created_at')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(DentalHistory)
class DentalHistoryAdmin(admin.ModelAdmin):
    list_display = ('dental_record', 'first_dental_visit', 'teeth_extracted', 'anesthesia_allergy', 'created_at')
    search_fields = ('dental_record__patient__username',)
    list_filter = ('first_dental_visit', 'teeth_extracted', 'anesthesia_allergy', 'created_at')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(PediatricDentalHistory)
class PediatricDentalHistoryAdmin(admin.ModelAdmin):
    list_display = ('dental_record', 'normal_pregnancy_birth', 'bottle_at_bedtime', 'thumb_sucking', 'created_at')
    search_fields = ('dental_record__patient__username',)
    list_filter = ('normal_pregnancy_birth', 'bottle_at_bedtime', 'thumb_sucking', 'created_at')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(DentalChart)
class DentalChartAdmin(admin.ModelAdmin):
    list_display = ('dental_record', 'tooth_number', 'tooth_type', 'condition', 'created_at')
    search_fields = ('dental_record__patient__username',)
    list_filter = ('tooth_type', 'condition', 'created_at')
    readonly_fields = ('created_at', 'updated_at')
