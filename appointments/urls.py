from django.urls import path
from . import views

app_name = 'appointments'

urlpatterns = [
    # Appointment CRUD
    path('', views.appointment_list, name='appointment_list'),
    path('schedule/', views.schedule_appointment, name='schedule_appointment'),
    path('schedule-for-patient/', views.schedule_for_patient, name='schedule_for_patient'),
    path('<int:appointment_id>/', views.appointment_detail, name='appointment_detail'),

    # Calendar (full page + HTMX fragments)
    path('calendar/', views.appointment_calendar, name='appointment_calendar'),
    path('calendar/month/', views.calendar_body_fragment, name='calendar_month_fragment'),
    path('calendar/body/', views.calendar_body_fragment, name='calendar_body_fragment'),
    path('calendar/day/', views.calendar_day_fragment, name='calendar_day_fragment'),
    path('calendar/export.ics', views.calendar_export_ics, name='calendar_export_ics'),

    # Appointment Settings (Admin Only)
    path('settings/', views.appointment_type_settings, name='appointment_type_settings'),
    path('settings/edit/<str:type_key>/', views.edit_appointment_type_default, name='edit_appointment_type_default'),
    path('settings/toggle/<int:default_id>/', views.toggle_appointment_type_default, name='toggle_appointment_type_default'),
]
