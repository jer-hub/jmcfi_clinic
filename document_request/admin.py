from django.contrib import admin
from .models import DocumentRequest, MedicalCertificate, DoctorSignature


@admin.register(DocumentRequest)
class DocumentRequestAdmin(admin.ModelAdmin):
    list_display = [
        'student',
        'document_type',
        'request_origin',
        'created_by',
        'purpose',
        'status',
        'medical_certificate',
        'created_at',
        'processed_by',
    ]
    list_filter = ['status', 'document_type', 'request_origin', 'created_at']
    search_fields = ['student__email', 'student__first_name', 'student__last_name', 'purpose']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']
    raw_id_fields = ['medical_certificate']
    
    fieldsets = (
        ('Request Information', {
            'fields': (
                'student',
                'document_type',
                'request_origin',
                'created_by',
                'purpose',
                'additional_info',
            )
        }),
        ('Status', {
            'fields': ('status', 'processed_by', 'rejection_reason')
        }),
        ('Linked Medical Certificate', {
            'fields': ('medical_certificate',),
            'description': 'Link this request to a Medical Certificate managed by Document Request'
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(MedicalCertificate)
class MedicalCertificateAdmin(admin.ModelAdmin):
    list_display = ['id', 'patient_name', 'user', 'status', 'certificate_date', 'physician_name', 'signed_by', 'signed_at', 'created_at']
    list_filter = ['status', 'gender', 'created_at']
    search_fields = ['patient_name', 'user__email', 'physician_name', 'diagnosis']
    readonly_fields = ['created_at', 'updated_at', 'signed_by', 'signed_at', 'signature_hash', 'signature_snapshot']


@admin.register(DoctorSignature)
class DoctorSignatureAdmin(admin.ModelAdmin):
    list_display = ['doctor', 'is_active', 'updated_by', 'updated_at']
    list_filter = ['is_active', 'updated_at']
    search_fields = ['doctor__first_name', 'doctor__last_name', 'doctor__email']
    readonly_fields = ['created_at', 'updated_at']
