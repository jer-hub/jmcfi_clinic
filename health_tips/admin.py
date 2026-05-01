from django.contrib import admin
from .models import HealthTip


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


@admin.register(HealthTip)
class HealthTipAdmin(BlockAdminRoleMixin, admin.ModelAdmin):
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
