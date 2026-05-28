from django.urls import path
from . import views
from .views.forms_cbvs import (
    HealthProfileListView,
    HealthProfileDetailView,
    HealthProfileEditView,
)
from .views.bulk import HealthProfileBulkReviewView
from .views._cbvs import (
    DentalListView, DentalDetailView, DentalEditView,
    PatientChartListView, PatientChartDetailView, PatientChartEditView,
    PrescriptionListView, PrescriptionDetailView, PrescriptionEditView,
    DentalServicesListView, DentalServicesDetailView, DentalServicesEditView,
)

app_name = 'health_forms_services'

urlpatterns = [
    # Patient picker APIs for transaction create flows
    path('api/search-patients/', views.search_patients, name='search_patients'),
    path('api/patient/<int:patient_id>/profile/', views.patient_profile_prefill, name='patient_profile_prefill'),

    # Health Profile Forms (class-based views)
    path('', HealthProfileListView.as_view(), name='forms_list'),
    path('new/', views.manual_entry, name='manual_entry'),
    path('<int:pk>/', HealthProfileDetailView.as_view(), name='form_detail'),
    path('<int:pk>/edit/', HealthProfileEditView.as_view(), name='edit_form'),
    path('<int:pk>/edit/section/', views.load_form_section, name='load_form_section'),
    path('<int:pk>/review/', views.review_form, name='review_form'),
    path('<int:pk>/delete/', views.delete_form, name='delete_form'),
    path('<int:pk>/export/', views.export_form_json, name='export_form'),
    path('<int:pk>/export/docx/', views.export_health_profile_docx, name='export_health_profile_docx'),
    path('bulk-review/', HealthProfileBulkReviewView.as_view(), name='bulk_review'),
    
    # Dental Health Forms (class-based views for list/detail/edit)
    path('dental/', DentalListView.as_view(), name='dental_forms_list'),
    path('dental/new/', views.create_dental_form, name='create_dental_form'),
    path('dental/<int:pk>/', DentalDetailView.as_view(), name='dental_form_detail'),
    path('dental/<int:pk>/edit/', DentalEditView.as_view(), name='edit_dental_form'),
    path('dental/<int:pk>/review/', views.review_dental_form, name='review_dental_form'),
    path('dental/<int:pk>/delete/', views.delete_dental_form, name='delete_dental_form'),
    path('dental/<int:pk>/export/docx/', views.export_dental_form_docx, name='export_dental_form_docx'),
    # Dental Chart API
    path('dental/<int:pk>/chart/api/', views.dental_form_chart_api_get, name='dental_chart_api_get'),
    path('dental/<int:pk>/chart/api/update/', views.dental_form_chart_api_update, name='dental_chart_api_update'),
    path('dental/<int:pk>/chart/api/bulk-update/', views.dental_form_chart_api_bulk_update, name='dental_chart_api_bulk_update'),
    path('dental/<int:pk>/chart/api/<int:tooth_id>/delete/', views.dental_form_chart_api_delete, name='dental_chart_api_delete'),
    
    # Patient Charts (class-based views for list/detail/edit)
    path('patient-chart/', PatientChartListView.as_view(), name='patient_chart_list'),
    path('patient-chart/new/', views.create_patient_chart, name='create_patient_chart'),
    path('patient-chart/<int:pk>/', PatientChartDetailView.as_view(), name='patient_chart_detail'),
    path('patient-chart/<int:pk>/edit/', PatientChartEditView.as_view(), name='edit_patient_chart'),
    path('patient-chart/<int:pk>/review/', views.review_patient_chart, name='review_patient_chart'),
    path('patient-chart/<int:pk>/delete/', views.delete_patient_chart, name='delete_patient_chart'),
    path('patient-chart/<int:pk>/export/docx/', views.export_patient_chart_docx, name='export_patient_chart_docx'),
    path('patient-chart/<int:pk>/entry/add/', views.add_chart_entry, name='add_chart_entry'),
    path('patient-chart/<int:pk>/entry/<int:entry_id>/delete/', views.delete_chart_entry, name='delete_chart_entry'),

    # Dental Services Request (class-based views for list/detail/edit)
    path('dental-services/', DentalServicesListView.as_view(), name='dental_services_list'),
    path('dental-services/new/', views.create_dental_services, name='create_dental_services'),
    path('dental-services/<int:pk>/', DentalServicesDetailView.as_view(), name='dental_services_detail'),
    path('dental-services/<int:pk>/edit/', DentalServicesEditView.as_view(), name='edit_dental_services'),
    path('dental-services/<int:pk>/review/', views.review_dental_services, name='review_dental_services'),
    path('dental-services/<int:pk>/delete/', views.delete_dental_services, name='delete_dental_services'),
    path('dental-services/<int:pk>/export/docx/', views.export_dental_services_docx, name='export_dental_services_docx'),

    # Prescriptions (class-based views for list/detail/edit)
    path('prescription/', PrescriptionListView.as_view(), name='prescription_list'),
    path('prescription/new/', views.create_prescription, name='create_prescription'),
    path('prescription/<int:pk>/', PrescriptionDetailView.as_view(), name='prescription_detail'),
    path('prescription/<int:pk>/edit/', PrescriptionEditView.as_view(), name='edit_prescription'),
    path('prescription/<int:pk>/review/', views.review_prescription, name='review_prescription'),
    path('prescription/<int:pk>/delete/', views.delete_prescription, name='delete_prescription'),
    path('prescription/<int:pk>/export/docx/', views.export_prescription_docx, name='export_prescription_docx'),
    path('prescription/<int:pk>/item/add/', views.add_prescription_item, name='add_prescription_item'),
    path('prescription/<int:pk>/item/<int:item_id>/delete/', views.delete_prescription_item, name='delete_prescription_item'),

]
