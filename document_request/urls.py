from django.urls import path
from . import views


app_name = 'document_request'

urlpatterns = [
    # Document/Certificate Request List
    path('', views.document_requests, name='document_requests'),
    
    # Submit New Request
    path('request/', views.request_document, name='request_document'),
    
    # Process Request (Doctor/Admin)
    path('process/<int:request_id>/', views.process_document, name='process_document'),
    
    # View Certificate
    path('view/<int:request_id>/', views.view_document, name='view_document'),
    
    # Print Certificate
    path('print/<int:request_id>/', views.print_document, name='print_document'),
    
    # Backwards compatibility URLs (aliased from old certificate URLs)
    path('certificates/', views.document_requests, name='certificate_requests'),
    path('certificates/request/', views.request_document, name='request_certificate'),
    path('certificates/process/<int:request_id>/', views.process_document, name='process_certificate'),
    path('certificates/view/<int:request_id>/', views.view_document, name='view_certificate'),
    path('certificates/print/<int:request_id>/', views.print_document, name='print_certificate'),
]
