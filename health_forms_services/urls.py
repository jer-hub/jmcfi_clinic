from django.urls import path
from . import views

app_name = 'health_forms_services'

urlpatterns = [
    # Health Profile Forms
    path('', views.health_forms_list, name='forms_list'),
    path('new/', views.manual_entry, name='manual_entry'),
    path('<int:pk>/', views.form_detail, name='form_detail'),
    path('<int:pk>/edit/', views.edit_form, name='edit_form'),
    path('<int:pk>/review/', views.review_form, name='review_form'),
    path('<int:pk>/delete/', views.delete_form, name='delete_form'),
    path('<int:pk>/export/', views.export_form_json, name='export_form'),
    path('<int:pk>/export/docx/', views.export_health_profile_docx, name='export_health_profile_docx'),
    
    # Dental Health Forms
    path('dental/', views.dental_forms_list, name='dental_forms_list'),
    path('dental/new/', views.create_dental_form, name='create_dental_form'),
    path('dental/<int:pk>/', views.dental_form_detail, name='dental_form_detail'),
    path('dental/<int:pk>/edit/', views.edit_dental_form, name='edit_dental_form'),
    path('dental/<int:pk>/review/', views.review_dental_form, name='review_dental_form'),
    path('dental/<int:pk>/delete/', views.delete_dental_form, name='delete_dental_form'),
    path('dental/<int:pk>/export/docx/', views.export_dental_form_docx, name='export_dental_form_docx'),
    # Dental Chart API
    path('dental/<int:pk>/chart/api/', views.dental_form_chart_api_get, name='dental_chart_api_get'),
    path('dental/<int:pk>/chart/api/update/', views.dental_form_chart_api_update, name='dental_chart_api_update'),
    path('dental/<int:pk>/chart/api/bulk-update/', views.dental_form_chart_api_bulk_update, name='dental_chart_api_bulk_update'),
    path('dental/<int:pk>/chart/api/<int:tooth_id>/delete/', views.dental_form_chart_api_delete, name='dental_chart_api_delete'),
    
    # Patient Charts (F-HSS-20-0002)
    path('patient-chart/', views.patient_chart_list, name='patient_chart_list'),
    path('patient-chart/new/', views.create_patient_chart, name='create_patient_chart'),
    path('patient-chart/<int:pk>/', views.patient_chart_detail, name='patient_chart_detail'),
    path('patient-chart/<int:pk>/edit/', views.edit_patient_chart, name='edit_patient_chart'),
    path('patient-chart/<int:pk>/review/', views.review_patient_chart, name='review_patient_chart'),
    path('patient-chart/<int:pk>/delete/', views.delete_patient_chart, name='delete_patient_chart'),
    path('patient-chart/<int:pk>/export/docx/', views.export_patient_chart_docx, name='export_patient_chart_docx'),
    path('patient-chart/<int:pk>/entry/add/', views.add_chart_entry, name='add_chart_entry'),
    path('patient-chart/<int:pk>/entry/<int:entry_id>/delete/', views.delete_chart_entry, name='delete_chart_entry'),

    # Dental Services Request (Dental Form 2)
    path('dental-services/', views.dental_services_list, name='dental_services_list'),
    path('dental-services/new/', views.create_dental_services, name='create_dental_services'),
    path('dental-services/<int:pk>/', views.dental_services_detail, name='dental_services_detail'),
    path('dental-services/<int:pk>/edit/', views.edit_dental_services, name='edit_dental_services'),
    path('dental-services/<int:pk>/review/', views.review_dental_services, name='review_dental_services'),
    path('dental-services/<int:pk>/delete/', views.delete_dental_services, name='delete_dental_services'),
    path('dental-services/<int:pk>/export/docx/', views.export_dental_services_docx, name='export_dental_services_docx'),

    # Prescriptions (F-HSS-20-0004)
    path('prescription/', views.prescription_list, name='prescription_list'),
    path('prescription/new/', views.create_prescription, name='create_prescription'),
    path('prescription/<int:pk>/', views.prescription_detail, name='prescription_detail'),
    path('prescription/<int:pk>/edit/', views.edit_prescription, name='edit_prescription'),
    path('prescription/<int:pk>/review/', views.review_prescription, name='review_prescription'),
    path('prescription/<int:pk>/delete/', views.delete_prescription, name='delete_prescription'),
    path('prescription/<int:pk>/export/docx/', views.export_prescription_docx, name='export_prescription_docx'),
    path('prescription/<int:pk>/item/add/', views.add_prescription_item, name='add_prescription_item'),
    path('prescription/<int:pk>/item/<int:item_id>/delete/', views.delete_prescription_item, name='delete_prescription_item'),

    # Medical Certificates (F-HSS-20-0005)
    path('medical-certificate/', views.medical_certificate_list, name='medical_certificate_list'),
    path('medical-certificate/new/', views.create_medical_certificate, name='create_medical_certificate'),
    path('medical-certificate/<int:pk>/', views.medical_certificate_detail, name='medical_certificate_detail'),
    path('medical-certificate/<int:pk>/edit/', views.edit_medical_certificate, name='edit_medical_certificate'),
    path('medical-certificate/<int:pk>/review/', views.review_medical_certificate, name='review_medical_certificate'),
    path('medical-certificate/<int:pk>/delete/', views.delete_medical_certificate, name='delete_medical_certificate'),
    path('medical-certificate/<int:pk>/export/docx/', views.export_medical_certificate_docx, name='export_medical_certificate_docx'),
    path('medical-certificate/my-signature/', views.my_signature, name='my_signature'),
]
