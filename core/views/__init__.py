"""Core views — re-exported for urls.py compatibility."""

from core.views.auth import (
    accept_invite,
    admin_login,
    csrf_failure,
    health_check,
    health_ready,
    logout_view,
    restricted_access,
)
from core.views.dashboard import dashboard
from core.views.notifications import (
    clear_all_notifications,
    create_system_notification,
    mark_all_notifications_read,
    mark_notification_read,
    notifications,
)
from core.views.patients import register_guest_patient, search_patients
from core.views.profile import (
    edit_profile,
    profile_required,
    profile_view,
    quick_edit_profile,
)
from core.views.user_management import (
    user_change_role,
    user_create,
    user_delete,
    user_detail,
    user_edit,
    user_management,
    user_resend_invite,
    user_reset_password,
    user_stats_cards,
    user_toggle_status,
)

__all__ = [
    'accept_invite',
    'admin_login',
    'clear_all_notifications',
    'create_system_notification',
    'csrf_failure',
    'dashboard',
    'edit_profile',
    'health_check',
    'health_ready',
    'logout_view',
    'mark_all_notifications_read',
    'mark_notification_read',
    'notifications',
    'profile_required',
    'profile_view',
    'quick_edit_profile',
    'register_guest_patient',
    'restricted_access',
    'search_patients',
    'user_change_role',
    'user_create',
    'user_delete',
    'user_detail',
    'user_edit',
    'user_management',
    'user_resend_invite',
    'user_reset_password',
    'user_stats_cards',
    'user_toggle_status',
]
