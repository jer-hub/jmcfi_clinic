from django.contrib import admin
from .models import Appointment, AppointmentTypeDefault


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ['id', 'patient', 'doctor', 'appointment_type', 'date', 'time', 'status', 'has_scheduling_conflict', 'created_at']
    list_filter = ['status', 'appointment_type', 'date']
    search_fields = ['patient__first_name', 'patient__last_name', 'patient__email', 
                     'doctor__first_name', 'doctor__last_name', 'reason']
    ordering = ['-date', '-time']
    date_hierarchy = 'date'
    
    def has_scheduling_conflict(self, obj):
        """Display whether appointment has scheduling conflicts with others."""
        if obj.status in ('cancelled', 'missed', 'completed'):
            return 'N/A'
        return 'Yes' if obj.has_conflict() else 'No'
    has_scheduling_conflict.short_description = 'Conflict?'


@admin.register(AppointmentTypeDefault)
class AppointmentTypeDefaultAdmin(admin.ModelAdmin):
    list_display = ['appointment_type', 'is_active', 'updated_at', 'updated_by']
    list_filter = ['is_active', 'appointment_type']
    search_fields = ['appointment_type']
    ordering = ['appointment_type']
