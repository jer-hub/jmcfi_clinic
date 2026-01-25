from django.urls import path
from django.views.generic import RedirectView
from . import views
from . import views_user_management
from . import views_appointment_settings


app_name = "management"
urlpatterns = [
    # Dashboard
    path('', views.dashboard, name='dashboard'),
    
    # Authentication
    path('logout/', views.logout_view, name='logout'),
    
    # Appointments - Redirect to new app
    path('appointments/', RedirectView.as_view(pattern_name='appointments:appointment_list', permanent=False), name='appointment_list'),
    path('appointments/schedule/', RedirectView.as_view(pattern_name='appointments:schedule_appointment', permanent=False), name='schedule_appointment'),
    path('appointments/<int:appointment_id>/', RedirectView.as_view(pattern_name='appointments:appointment_detail', permanent=False), name='appointment_detail'),
    
    # Appointment Settings (Admin Only)
    path('appointment-settings/', views_appointment_settings.appointment_type_settings, name='appointment_type_settings'),
    path('appointment-settings/edit/<str:type_key>/', views_appointment_settings.edit_appointment_type_default, name='edit_appointment_type_default'),
    path('appointment-settings/toggle/<int:default_id>/', views_appointment_settings.toggle_appointment_type_default, name='toggle_appointment_type_default'),
    path('appointment-settings/delete/<int:default_id>/', views_appointment_settings.delete_appointment_type_default, name='delete_appointment_type_default'),
    
    # Medical Records - Redirect to new app
    path('medical-records/', RedirectView.as_view(pattern_name='medical_records:medical_records', permanent=False), name='medical_records'),
    path('medical-records/<int:record_id>/details/', RedirectView.as_view(pattern_name='medical_records:medical_record_detail', permanent=False), name='medical_record_detail'),
    path('medical-records/create/<int:appointment_id>/', RedirectView.as_view(pattern_name='medical_records:create_medical_record', permanent=False), name='create_medical_record'),
    
    # Dental Records - Redirect to new app
    path('dental-records/', RedirectView.as_view(pattern_name='dental_records:dental_record_list', permanent=False), name='dental_record_list'),
    path('dental-records/create/', RedirectView.as_view(pattern_name='dental_records:dental_record_create', permanent=False), name='dental_record_create'),
    path('dental-records/<int:record_id>/', RedirectView.as_view(pattern_name='dental_records:dental_record_detail', permanent=False), name='dental_record_detail'),
    path('dental-records/<int:record_id>/edit/', RedirectView.as_view(pattern_name='dental_records:dental_record_edit', permanent=False), name='dental_record_edit'),
    path('dental-records/<int:record_id>/delete/', RedirectView.as_view(pattern_name='dental_records:dental_record_delete', permanent=False), name='dental_record_delete'),
    path('dental-records/<int:record_id>/export/', RedirectView.as_view(pattern_name='dental_records:dental_record_export_json', permanent=False), name='dental_record_export_json'),
    path('dental-records/<int:record_id>/chart/add/', RedirectView.as_view(pattern_name='dental_records:dental_chart_add_tooth', permanent=False), name='dental_chart_add_tooth'),
    path('dental-records/<int:record_id>/chart/<int:tooth_id>/delete/', RedirectView.as_view(pattern_name='dental_records:dental_chart_delete_tooth', permanent=False), name='dental_chart_delete_tooth'),
    path('my-dental-records/', RedirectView.as_view(pattern_name='dental_records:my_dental_records', permanent=False), name='my_dental_records'),
    path('my-dental-records/<int:record_id>/', RedirectView.as_view(pattern_name='dental_records:my_dental_record_detail', permanent=False), name='my_dental_record_detail'),
    
    # Certificate Requests
    path('certificates/', views.certificate_requests, name='certificate_requests'),
    path('certificates/request/', views.request_certificate, name='request_certificate'),
    path('certificates/process/<int:request_id>/', views.process_certificate, name='process_certificate'),
    path('certificates/view/<int:request_id>/', views.view_certificate, name='view_certificate'),
    path('certificates/print/<int:request_id>/', views.print_certificate, name='print_certificate'),
    
    # Health Tips
    path('health-tips/', views.health_tips, name='health_tips'),
    path('health-tips/create/', views.create_health_tip, name='create_health_tip'),
    path('health-tips/<int:tip_id>/edit/', views.edit_health_tip, name='edit_health_tip'),
    path('health-tips/<int:tip_id>/delete/', views.delete_health_tip, name='delete_health_tip'),
    path('health-tips/<int:tip_id>/toggle-status/', views.toggle_health_tip_status, name='toggle_health_tip_status'),
    
    # Notifications
    path('notifications/', views.notifications, name='notifications'),
    path('notifications/<int:notification_id>/read/', views.mark_notification_read, name='mark_notification_read'),
    path('notifications/mark-all-read/', views.mark_all_notifications_read, name='mark_all_notifications_read'),
    path('notifications/create-system/', views.create_system_notification, name='create_system_notification'),
    
    # Feedback
    path('feedback/', views.feedback_list, name='feedback_list'),
    path('feedback/submit/', views.submit_feedback, name='submit_feedback'),
    path('feedback/submit/<int:appointment_id>/', views.submit_feedback, name='submit_feedback_appointment'),
    
    # Profile
    path('profile/', views.profile_view, name='profile'),
    path('profile/edit/', views.edit_profile, name='edit_profile'),
    path('profile/quick-edit/', views.quick_edit_profile, name='quick_edit_profile'),
    
    # User Management (Admin Only)
    path('users/', views_user_management.user_management, name='user_management'),
    path('users/create/', views_user_management.user_create, name='user_create'),
    path('users/<int:user_id>/', views_user_management.user_detail, name='user_detail'),
    path('users/<int:user_id>/edit/', views_user_management.user_edit, name='user_edit'),
    path('users/<int:user_id>/delete/', views_user_management.user_delete, name='user_delete'),
    path('users/<int:user_id>/toggle-status/', views_user_management.user_toggle_status, name='user_toggle_status'),
    path('users/<int:user_id>/reset-password/', views_user_management.user_reset_password, name='user_reset_password'),
]
