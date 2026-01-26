from django.urls import path
from . import views

app_name = 'appointments'

urlpatterns = [
    # Appointment CRUD
    path('', views.appointment_list, name='appointment_list'),
    path('schedule/', views.schedule_appointment, name='schedule_appointment'),
    path('<int:appointment_id>/', views.appointment_detail, name='appointment_detail'),
    
    # Appointment Settings (Admin Only)
    path('settings/', views.appointment_type_settings, name='appointment_type_settings'),
    path('settings/edit/<str:type_key>/', views.edit_appointment_type_default, name='edit_appointment_type_default'),
    path('settings/toggle/<int:default_id>/', views.toggle_appointment_type_default, name='toggle_appointment_type_default'),
    path('settings/delete/<int:default_id>/', views.delete_appointment_type_default, name='delete_appointment_type_default'),
]
