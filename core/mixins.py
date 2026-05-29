"""Class-based view mixins for HTMX-safe access control."""

from django.contrib.auth.mixins import AccessMixin, LoginRequiredMixin

from .access_control import AccessReason, access_denied_response


class RestrictedAccessMixin(AccessMixin):
    """Return 401/403 + HX-Redirect instead of swapping login HTML into hx-target."""

    permission_denied_reason = AccessReason.FORBIDDEN
    permission_denied_status = 403
    permission_denied_use_admin_login = False

    def handle_no_permission(self):
        if self.raise_exception:
            from django.core.exceptions import PermissionDenied

            raise PermissionDenied
        return access_denied_response(
            self.request,
            status_code=self.permission_denied_status,
            reason=self.permission_denied_reason,
            use_admin_login=self.permission_denied_use_admin_login,
        )


class HtmxLoginRequiredMixin(RestrictedAccessMixin, LoginRequiredMixin):
    permission_denied_reason = AccessReason.UNAUTHENTICATED
    permission_denied_status = 401


class RoleRequiredMixin(RestrictedAccessMixin):
    """
    Require authenticated user with one of ``required_roles``.

        class StaffView(RoleRequiredMixin, View):
            required_roles = ('staff', 'doctor')
    """

    required_roles: tuple[str, ...] = ()

    def has_permission(self):
        if not self.request.user.is_authenticated:
            return False
        from .roles import role_matches

        return role_matches(self.request.user.role, *self.required_roles)

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            self.permission_denied_status = 401
            self.permission_denied_reason = AccessReason.UNAUTHENTICATED
        else:
            self.permission_denied_status = 403
            self.permission_denied_reason = AccessReason.FORBIDDEN
        return super().handle_no_permission()
