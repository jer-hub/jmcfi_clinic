from django.urls import path
from . import views


app_name = "management"
urlpatterns = [
    # Dashboard
    path('', views.dashboard, name='dashboard'),
    
    # Authentication
    path('logout/', views.logout_view, name='logout'),
    
    # Appointments
    path('appointments/', views.appointment_list, name='appointment_list'),
    path('appointments/schedule/', views.schedule_appointment, name='schedule_appointment'),
    path('appointments/<int:appointment_id>/', views.appointment_detail, name='appointment_detail'),
    
    # Medical Records
    path('medical-records/', views.medical_records, name='medical_records'),
    path('medical-records/<int:record_id>/details/', views.medical_record_detail, name='medical_record_detail'),
    path('medical-records/create/<int:appointment_id>/', views.create_medical_record, name='create_medical_record'),
    
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
]
