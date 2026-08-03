from django.contrib import admin

from core.admin_mixins import BlockAdminRoleMixin

from .models import ConcernRecord


@admin.register(ConcernRecord)
class ConcernRecordAdmin(BlockAdminRoleMixin, admin.ModelAdmin):
    list_display = (
        'date',
        'time',
        'patient_user',
        'last_name',
        'first_name',
        'affiliation_type',
        'college_department',
        'department_other',
        'course_program',
        'year_level',
        'created_by',
        'created_at',
    )
    list_filter = (
        'date',
        'affiliation_type',
        'college_department',
        'course_program',
        'year_level',
    )
    search_fields = (
        'first_name',
        'last_name',
        'middle_name',
        'department_other',
        'concerns',
        'disposition',
    )
    readonly_fields = ('created_at', 'updated_at')
    raw_id_fields = ('college_department', 'created_by')
    date_hierarchy = 'date'
