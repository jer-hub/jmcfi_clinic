from django.contrib import admin
from .models import Feedback


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ('student', 'rating', 'appointment', 'is_anonymous', 'created_at')
    search_fields = ('student__username', 'student__email', 'comments', 'suggestions')
    list_filter = ('rating', 'is_anonymous', 'created_at')
    readonly_fields = ('created_at',)
    ordering = ['-created_at']
    
    fieldsets = (
        ('Feedback Information', {
            'fields': ('student', 'appointment', 'rating', 'is_anonymous')
        }),
        ('Content', {
            'fields': ('comments', 'suggestions')
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
