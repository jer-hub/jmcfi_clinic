from django.contrib import admin
from .models import DocumentRequest


@admin.register(DocumentRequest)
class DocumentRequestAdmin(admin.ModelAdmin):
    list_display = ['student', 'document_type', 'purpose', 'status', 'created_at', 'processed_by']
    list_filter = ['status', 'document_type', 'created_at']
    search_fields = ['student__email', 'student__first_name', 'student__last_name', 'purpose']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']
    
    fieldsets = (
        ('Request Information', {
            'fields': ('student', 'document_type', 'purpose', 'additional_info')
        }),
        ('Status', {
            'fields': ('status', 'processed_by', 'rejection_reason')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
