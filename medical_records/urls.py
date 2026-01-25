from django.urls import path
from . import views

app_name = 'medical_records'

urlpatterns = [
    path('', views.medical_records, name='medical_records'),
    path('<int:record_id>/details/', views.medical_record_detail, name='medical_record_detail'),
    path('create/<int:appointment_id>/', views.create_medical_record, name='create_medical_record'),
]
