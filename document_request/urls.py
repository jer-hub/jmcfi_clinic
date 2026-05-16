from django.urls import path
from . import views


app_name = 'document_request'

urlpatterns = [
    # Document/Certificate Request List
    path('', views.document_requests, name='document_requests'),
    
    # Submit New Request
    path('request/', views.request_document, name='request_document'),

    # Clinician signature (doctor/staff/admin)
    path('signature/', views.clinician_signature, name='clinician_signature'),

    # Request detail hub (view + process)
    path('<int:request_id>/', views.document_request_detail, name='document_request_detail'),

    # Legacy URLs → detail hub
    path('process/<int:request_id>/', views.process_document, name='process_document'),
    
    # Edit Medical Certificate
    path('certificate/<int:cert_id>/edit/', views.edit_medical_certificate, name='edit_medical_certificate'),
    
    # Preview Medical Certificate
    path('certificate/<int:cert_id>/preview/', views.preview_medical_certificate, name='preview_medical_certificate'),
    
    # Download Medical Certificate PDF
    path('certificate/<int:cert_id>/download/', views.download_medical_certificate_pdf, name='download_medical_certificate_pdf'),
    
    # View Certificate
    path('view/<int:request_id>/', views.view_document, name='view_document'),
    
]
