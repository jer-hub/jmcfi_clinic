from django.contrib import admin
from .models import (
    StudentProfile, StaffProfile, Appointment, MedicalRecord, 
    CertificateRequest, HealthTip, Notification, Feedback
)

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

@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ('student', 'doctor', 'appointment_type', 'date', 'time', 'status', 'created_at')
    search_fields = ('student__username', 'doctor__username', 'reason')
    list_filter = ('appointment_type', 'status', 'date', 'created_at')
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'date'

@admin.register(MedicalRecord)
class MedicalRecordAdmin(admin.ModelAdmin):
    list_display = ('student', 'doctor', 'diagnosis', 'follow_up_required', 'created_at')
    search_fields = ('student__username', 'doctor__username', 'diagnosis', 'treatment')
    list_filter = ('follow_up_required', 'created_at')
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'created_at'

@admin.register(CertificateRequest)
class CertificateRequestAdmin(admin.ModelAdmin):
    list_display = ('student', 'certificate_type', 'purpose', 'status', 'processed_by', 'created_at')
    search_fields = ('student__username', 'purpose')
    list_filter = ('certificate_type', 'status', 'created_at')
    readonly_fields = ('created_at', 'updated_at')
    actions = ['approve_certificates', 'reject_certificates']

    def approve_certificates(self, request, queryset):
        queryset.update(status='approved')
    approve_certificates.short_description = "Approve selected certificates"

    def reject_certificates(self, request, queryset):
        queryset.update(status='rejected')
    reject_certificates.short_description = "Reject selected certificates"

@admin.register(HealthTip)
class HealthTipAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'created_by', 'is_active', 'created_at')
    search_fields = ('title', 'content')
    list_filter = ('category', 'is_active', 'created_at')
    readonly_fields = ('created_at', 'updated_at')
    actions = ['make_active', 'make_inactive']

    def make_active(self, request, queryset):
        queryset.update(is_active=True)
    make_active.short_description = "Mark selected tips as active"

    def make_inactive(self, request, queryset):
        queryset.update(is_active=False)
    make_inactive.short_description = "Mark selected tips as inactive"

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

@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ('student', 'rating', 'appointment', 'is_anonymous', 'created_at')
    search_fields = ('student__username', 'comments', 'suggestions')
    list_filter = ('rating', 'is_anonymous', 'created_at')
    readonly_fields = ('created_at',)
