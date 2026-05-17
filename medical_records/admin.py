from django.contrib import admin
from core.admin_mixins import BlockAdminRoleMixin
from .models import MedicalRecord


@admin.register(MedicalRecord)
class MedicalRecordAdmin(BlockAdminRoleMixin, admin.ModelAdmin):
    list_display = ('id', 'patient', 'doctor', 'diagnosis', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('patient__first_name', 'patient__last_name', 'patient__email', 
                     'doctor__first_name', 'doctor__last_name', 'diagnosis', 'treatment')
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
