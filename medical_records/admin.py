from django.contrib import admin
from .models import MedicalRecord


@admin.register(MedicalRecord)
class MedicalRecordAdmin(admin.ModelAdmin):
    list_display = ('id', 'student', 'doctor', 'diagnosis', 'follow_up_required', 'created_at')
    list_filter = ('follow_up_required', 'created_at')
    search_fields = ('student__first_name', 'student__last_name', 'student__email', 
                     'doctor__first_name', 'doctor__last_name', 'diagnosis', 'treatment')
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
