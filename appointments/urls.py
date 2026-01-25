from django.urls import path
from . import views

app_name = 'appointments'

urlpatterns = [
    path('', views.appointment_list, name='appointment_list'),
    path('schedule/', views.schedule_appointment, name='schedule_appointment'),
    path('<int:appointment_id>/', views.appointment_detail, name='appointment_detail'),
]
