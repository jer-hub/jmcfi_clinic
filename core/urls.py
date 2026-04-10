from django.urls import path
from . import views

app_name = "core"

urlpatterns = [
    # Dashboard
    path('', views.dashboard, name='dashboard'),
    
    # Authentication
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
    
    # User Management (Admin Only)
    path('users/', views.user_management, name='user_management'),
    path('users/create/', views.user_create, name='user_create'),
    path('users/<int:user_id>/', views.user_detail, name='user_detail'),
    path('users/<int:user_id>/edit/', views.user_edit, name='user_edit'),
    path('users/<int:user_id>/delete/', views.user_delete, name='user_delete'),
    path('users/<int:user_id>/toggle-status/', views.user_toggle_status, name='user_toggle_status'),
    path('users/<int:user_id>/reset-password/', views.user_reset_password, name='user_reset_password'),
    
    # Search
    path('search/students/', views.search_students, name='search_students'),
]
