from django.urls import path
from . import views
from . import user_mgmt_views
from . import settings_views

app_name = "core"

urlpatterns = [
    # Dashboard
    path('', views.dashboard, name='dashboard'),
    
    # Authentication
    path('auth/admin-login/', views.admin_login, name='admin_login'),
    path('auth/invite/accept/<str:token>/', views.accept_invite, name='accept_invite'),
    path('logout/', views.logout_view, name='logout'),
    
    # Notifications
    path('notifications/', views.notifications, name='notifications'),
    path('notifications/<int:notification_id>/read/', views.mark_notification_read, name='mark_notification_read'),
    path('notifications/mark-all-read/', views.mark_all_notifications_read, name='mark_all_notifications_read'),
    path('notifications/clear-all/', views.clear_all_notifications, name='clear_all_notifications'),
    path('notifications/create-system/', views.create_system_notification, name='create_system_notification'),
    
    # Profile
    path('profile/', views.profile_view, name='profile'),
    path('profile/edit/', views.edit_profile, name='edit_profile'),
    path('profile/quick-edit/', views.quick_edit_profile, name='quick_edit_profile'),
    path('profile/required/', views.profile_required, name='profile_required'),
    path('profile/preferences/', settings_views.profile_preferences, name='profile_preferences'),
    
    # User Management (Admin Only)
    path('users/', views.user_management, name='user_management'),
    path('users/stats/', views.user_stats_cards, name='user_stats_cards'),
    path('users/deleted/', user_mgmt_views.deleted_user_management, name='deleted_user_management'),
    path('users/create/', views.user_create, name='user_create'),
    path('users/<int:user_id>/', views.user_detail, name='user_detail'),
    path('users/<int:user_id>/edit/', views.user_edit, name='user_edit'),
    path('users/<int:user_id>/delete/', views.user_delete, name='user_delete'),
    path('users/<int:user_id>/toggle-status/', views.user_toggle_status, name='user_toggle_status'),
    path('users/<int:user_id>/reset-password/', views.user_reset_password, name='user_reset_password'),
    path('users/<int:user_id>/resend-invite/', views.user_resend_invite, name='user_resend_invite'),
    # Extended user management
    path('users/bulk-action/', user_mgmt_views.user_bulk_action, name='user_bulk_action'),
    path('users/<int:user_id>/restore/', user_mgmt_views.user_restore, name='user_restore'),
    path('users/deleted/bulk-restore/', user_mgmt_views.deleted_user_bulk_restore, name='deleted_user_bulk_restore'),
    path('users/deleted/bulk-action/', user_mgmt_views.deleted_user_bulk_action, name='deleted_user_bulk_action'),
    path('users/deleted/<int:user_id>/delete/', user_mgmt_views.deleted_user_permanent_delete, name='deleted_user_permanent_delete'),
    path('users/<int:user_id>/audit-log/', user_mgmt_views.user_audit_log, name='user_audit_log'),
    path('users/export/csv/', user_mgmt_views.user_export_csv, name='user_export_csv'),
    path('users/cleanup/stale/', user_mgmt_views.user_cleanup_stale, name='user_cleanup_stale'),
    
    # Search
    path('search/students/', views.search_students, name='search_students'),

    # System settings (admin)
    path('settings/', settings_views.settings_hub, name='settings_hub'),
    path('settings/clinic/', settings_views.settings_clinic, name='settings_clinic'),
    path('settings/roles/', settings_views.settings_roles, name='settings_roles'),
    path('settings/roles/<str:role>/', settings_views.settings_role_edit, name='settings_role_edit'),
    path('settings/audit/', settings_views.settings_audit, name='settings_audit'),
]
