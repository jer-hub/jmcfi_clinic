from django.contrib import admin
from .models import DocumentRequest, StudentRequestSchedule


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
                'scheduled_for_date',
                'scheduled_for_time',
            )
        }),
        ('Status', {
            'fields': ('status', 'processed_by', 'rejection_reason')
        }),
        ('Linked Medical Certificate', {
            'fields': ('medical_certificate',),
            'description': 'Link this request to a Medical Certificate from Health Forms Services'
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(StudentRequestSchedule)
class StudentRequestScheduleAdmin(admin.ModelAdmin):
    list_display = ['student', 'is_active', 'start_time', 'end_time', 'updated_by', 'updated_at']
    list_filter = ['is_active', 'allowed_days']
    search_fields = ['student__email', 'student__first_name', 'student__last_name']
    readonly_fields = ['created_at', 'updated_at']
