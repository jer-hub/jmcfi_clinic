from django.urls import path
from . import views

app_name = 'dental_records'

urlpatterns = [
    # Dental Records (Staff/Doctor/Admin)
    path('', views.dental_record_list, name='dental_record_list'),
    path('create/', views.dental_record_create, name='dental_record_create'),
    path('<int:record_id>/', views.dental_record_detail, name='dental_record_detail'),
    path('<int:record_id>/edit/', views.dental_record_edit, name='dental_record_edit'),
    path('<int:record_id>/complete-appointment/', views.complete_appointment, name='complete_appointment'),
    path('<int:record_id>/mark-completed/', views.mark_record_completed, name='mark_record_completed'),
    path('<int:record_id>/delete/', views.dental_record_delete, name='dental_record_delete'),
    path('<int:record_id>/export/', views.dental_record_export_json, name='dental_record_export_json'),
    path('<int:record_id>/chart/add/', views.dental_chart_add_tooth, name='dental_chart_add_tooth'),
    path('<int:record_id>/chart/<int:tooth_id>/delete/', views.dental_chart_delete_tooth, name='dental_chart_delete_tooth'),
    
    # Interactive Dental Chart API Endpoints
    path('<int:record_id>/chart/api/', views.dental_chart_api_get, name='dental_chart_api_get'),
    path('<int:record_id>/chart/api/update/', views.dental_chart_api_update_tooth, name='dental_chart_api_update_tooth'),
    path('<int:record_id>/chart/api/bulk-update/', views.dental_chart_api_bulk_update, name='dental_chart_api_bulk_update'),
    path('<int:record_id>/chart/api/<int:tooth_id>/delete/', views.dental_chart_api_delete_tooth, name='dental_chart_api_delete_tooth'),
    path('<int:record_id>/chart/api/<int:tooth_id>/surface/', views.dental_chart_api_update_surface, name='dental_chart_api_update_surface'),
    path('<int:record_id>/chart/api/<int:tooth_id>/surface/<int:surface_id>/delete/', views.dental_chart_api_delete_surface, name='dental_chart_api_delete_surface'),
    path('<int:record_id>/chart/api/export/', views.dental_chart_api_export, name='dental_chart_api_export'),
    path('<int:record_id>/chart/api/snapshots/', views.dental_chart_api_get_snapshots, name='dental_chart_api_get_snapshots'),
    path('<int:record_id>/chart/api/snapshots/save/', views.dental_chart_api_save_snapshot, name='dental_chart_api_save_snapshot'),
    path('<int:record_id>/chart/api/snapshots/<int:snapshot_id>/', views.dental_chart_api_get_snapshot, name='dental_chart_api_get_snapshot'),
    path('<int:record_id>/chart/api/snapshots/compare/', views.dental_chart_api_compare_snapshots, name='dental_chart_api_compare_snapshots'),
    
    # Progress Notes API
    path('<int:record_id>/progress-notes/', views.progress_note_list, name='progress_note_list'),
    path('<int:record_id>/progress-notes/add/', views.progress_note_create, name='progress_note_create'),
    path('<int:record_id>/progress-notes/<int:note_id>/delete/', views.progress_note_delete, name='progress_note_delete'),
    
    # API endpoints
    path('api/search-patients/', views.search_patients, name='search_patients'),
    path('api/patient/<int:patient_id>/profile/', views.get_patient_profile, name='get_patient_profile'),
    
    # My Dental Records (Patient View)
    path('my-dental-records/', views.my_dental_records, name='my_dental_records'),
    path('my-dental-records/<int:record_id>/', views.my_dental_record_detail, name='my_dental_record_detail'),

    # Student self-intake (after appointment is confirmed)
    path('intake/<int:appointment_id>/', views.student_dental_intake, name='student_dental_intake'),
]
