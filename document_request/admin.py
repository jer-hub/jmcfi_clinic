from django.contrib import admin
from core.admin_mixins import BlockAdminRoleMixin
from .models import ClinicianSignature, DocumentRequest, DocumentRequestEvent, MedicalCertificate

DoctorSignature = ClinicianSignature


@admin.register(DocumentRequest)
class DocumentRequestAdmin(BlockAdminRoleMixin, admin.ModelAdmin):
    list_display = [
        'patient',
        'document_type',
        'request_origin',
        'created_by',
        'assigned_to',
        'purpose',
        'status',
        'medical_certificate',
        'created_at',
        'processed_by',
    ]
    list_filter = ['status', 'document_type', 'request_origin', 'created_at']
    search_fields = ['patient__email', 'patient__first_name', 'patient__last_name', 'purpose']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']
    raw_id_fields = ['medical_certificate', 'assigned_to']

    fieldsets = (
        ('Request Information', {
            'fields': (
                'patient',
                'document_type',
                'request_origin',
                'created_by',
                'assigned_to',
                'purpose',
                'additional_info',
            )
        }),
        ('Status', {
            'fields': ('status', 'processed_by', 'rejection_reason')
        }),
        ('Linked Medical Certificate', {
            'fields': ('medical_certificate',),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(MedicalCertificate)
class MedicalCertificateAdmin(BlockAdminRoleMixin, admin.ModelAdmin):
    list_display = [
        'id', 'patient_name', 'user', 'status', 'certificate_date',
        'physician_name', 'signed_by', 'signed_at', 'created_at',
    ]
    list_filter = ['status', 'gender', 'created_at']
    search_fields = ['patient_name', 'user__email', 'physician_name', 'diagnosis']
    readonly_fields = [
        'created_at', 'updated_at', 'signed_by', 'signed_at',
        'signature_hash', 'signature_snapshot',
    ]


@admin.register(ClinicianSignature)
class ClinicianSignatureAdmin(BlockAdminRoleMixin, admin.ModelAdmin):
    list_display = ['doctor', 'is_active', 'updated_by', 'updated_at']
    list_filter = ['is_active', 'updated_at']
    search_fields = ['doctor__first_name', 'doctor__last_name', 'doctor__email']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(DocumentRequestEvent)
class DocumentRequestEventAdmin(BlockAdminRoleMixin, admin.ModelAdmin):
    list_display = ['request', 'event_type', 'actor', 'created_at']
    list_filter = ['event_type', 'created_at']
    search_fields = ['request__patient__email', 'actor__email']
    readonly_fields = ['created_at']
