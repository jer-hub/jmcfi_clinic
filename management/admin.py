from django.contrib import admin
from .models import (
    StudentProfile, StaffProfile, 
    Notification
)
# Note: Feedback admin is now handled by feedback app
# Note: HealthTip admin is now handled by health_tips app

@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ('student_id', 'user', 'phone', 'blood_type', 'has_profile_image', 'created_at')
    search_fields = ('student_id', 'user__username', 'user__email', 'user__first_name', 'user__last_name')
    list_filter = ('blood_type', 'created_at')
    readonly_fields = ('created_at', 'updated_at')
    fields = ('user', 'student_id', 'profile_image', 'date_of_birth', 'phone', 
             'emergency_contact', 'emergency_phone', 'blood_type', 'allergies', 
             'medical_conditions', 'created_at', 'updated_at')

    def has_profile_image(self, obj):
        return bool(obj.profile_image)
    has_profile_image.boolean = True
    has_profile_image.short_description = 'Has Image'

@admin.register(StaffProfile)
class StaffProfileAdmin(admin.ModelAdmin):
    list_display = ('staff_id', 'user', 'department', 'specialization', 'has_profile_image', 'created_at')
    search_fields = ('staff_id', 'user__username', 'user__email', 'user__first_name', 'user__last_name', 'department')
    list_filter = ('department', 'created_at')
    readonly_fields = ('created_at', 'updated_at')
    fields = ('user', 'staff_id', 'profile_image', 'department', 'specialization', 
             'license_number', 'phone', 'created_at', 'updated_at')

    def has_profile_image(self, obj):
        return bool(obj.profile_image)
    has_profile_image.boolean = True
    has_profile_image.short_description = 'Has Image'

# Note: CertificateRequest admin is now handled by document_request app
# Note: HealthTip admin is now handled by health_tips app

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'title', 'notification_type', 'is_read', 'created_at')
    search_fields = ('user__username', 'title', 'message')
    list_filter = ('notification_type', 'is_read', 'created_at')
    readonly_fields = ('created_at',)
    actions = ['mark_as_read', 'mark_as_unread']

    def mark_as_read(self, request, queryset):
        queryset.update(is_read=True)
    mark_as_read.short_description = "Mark selected notifications as read"

    def mark_as_unread(self, request, queryset):
        queryset.update(is_read=False)
    mark_as_unread.short_description = "Mark selected notifications as unread"

# Note: Feedback admin is now handled by feedback app
