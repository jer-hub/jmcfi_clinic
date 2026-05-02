"""
Shared admin mixins for consistent Django Admin access control.

BlockAdminRoleMixin: Restricts Django Admin access for custom admin-role users.
- Superusers always have full access.
- Custom admin-role users (role='admin', is_superuser=False) are BLOCKED.
- Staff/doctor/student users with is_staff=True are ALLOWED.

Rationale: Clinical data (pharmacy, health forms, dental/medical records,
feedback) should be managed by clinical staff or superusers, not by
general administrative users.  Operational data (users, appointments,
analytics) remains accessible to admin-role users via Django Admin.
"""


class BlockAdminRoleMixin:
    """Prevent custom admin-role users from accessing Django Admin for this model."""

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
