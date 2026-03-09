from django.contrib import admin
from .models import (
    HealthTrendRecord, PredictiveInsight, ResourceUtilization,
    ComplianceReport, FinancialRecord, ExportLog,
)


@admin.register(HealthTrendRecord)
class HealthTrendRecordAdmin(admin.ModelAdmin):
    list_display = ('illness_category', 'academic_year', 'semester', 'case_count', 'updated_at')
    list_filter = ('academic_year', 'semester')
    search_fields = ('illness_category', 'notes')
    ordering = ('-academic_year', 'semester', '-case_count')


@admin.register(PredictiveInsight)
class PredictiveInsightAdmin(admin.ModelAdmin):
    list_display = ('title', 'insight_type', 'risk_level', 'period_start', 'period_end', 'created_at')
    list_filter = ('insight_type', 'risk_level')
    search_fields = ('title', 'description')
    readonly_fields = ('data_json', 'created_at')


@admin.register(ResourceUtilization)
class ResourceUtilizationAdmin(admin.ModelAdmin):
    list_display = ('date', 'total_consultations', 'avg_consultation_minutes', 'patient_throughput', 'staff_on_duty', 'efficiency_score')
    list_filter = ('date',)
    ordering = ('-date',)


@admin.register(ComplianceReport)
class ComplianceReportAdmin(admin.ModelAdmin):
    list_display = ('title', 'report_type', 'status', 'period_start', 'period_end', 'created_at')
    list_filter = ('report_type', 'status')
    search_fields = ('title', 'description')
    readonly_fields = ('data_json', 'created_at', 'updated_at')


@admin.register(FinancialRecord)
class FinancialRecordAdmin(admin.ModelAdmin):
    list_display = ('date', 'category', 'description', 'amount', 'is_expense', 'recorded_by')
    list_filter = ('category', 'is_expense', 'date')
    search_fields = ('description', 'reference_number')
    ordering = ('-date',)


@admin.register(ExportLog)
class ExportLogAdmin(admin.ModelAdmin):
    list_display = ('report_name', 'export_format', 'exported_by', 'created_at')
    list_filter = ('export_format',)
    readonly_fields = ('created_at',)
