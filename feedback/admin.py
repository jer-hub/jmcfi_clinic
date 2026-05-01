from django.contrib import admin
from .models import Feedback


class BlockAdminRoleMixin:
    """Prevent custom admin-role users from accessing this app in Django Admin."""

    def _allow_access(self, request):
        return request.user.is_superuser or request.user.role != 'admin'

    def has_module_permission(self, request):
        return self._allow_access(request) and super().has_module_permission(request)

    def has_view_permission(self, request, obj=None):
        return self._allow_access(request) and super().has_view_permission(request, obj=obj)

    def has_add_permission(self, request):
        return self._allow_access(request) and super().has_add_permission(request)

    def has_change_permission(self, request, obj=None):
        return self._allow_access(request) and super().has_change_permission(request, obj=obj)

    def has_delete_permission(self, request, obj=None):
        return self._allow_access(request) and super().has_delete_permission(request, obj=obj)


@admin.register(Feedback)
class FeedbackAdmin(BlockAdminRoleMixin, admin.ModelAdmin):
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
