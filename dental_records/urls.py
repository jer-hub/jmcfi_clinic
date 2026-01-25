from django.urls import path
from . import views

app_name = 'dental_records'

urlpatterns = [
    # Dental Records (Staff/Doctor/Admin)
    path('', views.dental_record_list, name='dental_record_list'),
    path('create/', views.dental_record_create, name='dental_record_create'),
    path('<int:record_id>/', views.dental_record_detail, name='dental_record_detail'),
    path('<int:record_id>/edit/', views.dental_record_edit, name='dental_record_edit'),
    path('<int:record_id>/delete/', views.dental_record_delete, name='dental_record_delete'),
    path('<int:record_id>/export/', views.dental_record_export_json, name='dental_record_export_json'),
    path('<int:record_id>/chart/add/', views.dental_chart_add_tooth, name='dental_chart_add_tooth'),
    path('<int:record_id>/chart/<int:tooth_id>/delete/', views.dental_chart_delete_tooth, name='dental_chart_delete_tooth'),
    
    # API endpoints
    path('api/search-patients/', views.search_patients, name='search_patients'),
    path('api/patient/<int:patient_id>/profile/', views.get_patient_profile, name='get_patient_profile'),
    
    # My Dental Records (Patient View)
    path('my-dental-records/', views.my_dental_records, name='my_dental_records'),
    path('my-dental-records/<int:record_id>/', views.my_dental_record_detail, name='my_dental_record_detail'),
]
