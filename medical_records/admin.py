from django.contrib import admin
from core.admin_mixins import BlockAdminRoleMixin
from .models import MedicalRecord


@admin.register(MedicalRecord)
class MedicalRecordAdmin(BlockAdminRoleMixin, admin.ModelAdmin):
    list_display = ('id', 'student', 'doctor', 'diagnosis', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('student__first_name', 'student__last_name', 'student__email', 
                     'doctor__first_name', 'doctor__last_name', 'diagnosis', 'treatment')
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
