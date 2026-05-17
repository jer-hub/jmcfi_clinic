from django.contrib import admin
from core.admin_mixins import BlockAdminRoleMixin
from .models import Feedback


@admin.register(Feedback)
class FeedbackAdmin(BlockAdminRoleMixin, admin.ModelAdmin):
    list_display = ('patient', 'rating', 'appointment', 'is_anonymous', 'created_at')
    search_fields = ('patient__username', 'patient__email', 'comments', 'suggestions')
    list_filter = ('rating', 'is_anonymous', 'created_at')
    readonly_fields = ('created_at',)
    ordering = ['-created_at']
    
    fieldsets = (
        ('Feedback Information', {
            'fields': ('patient', 'appointment', 'rating', 'is_anonymous')
        }),
        ('Content', {
            'fields': ('comments', 'suggestions')
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
