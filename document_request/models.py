from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class DocumentRequest(models.Model):
    """Model for certificate/document requests from students."""
    
    DOCUMENT_TYPES = [
        ('medical_certificate', 'Medical Certificate'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('rejected', 'Rejected'),
    ]

    student = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='document_requests'
    )
    document_type = models.CharField(max_length=30, choices=DOCUMENT_TYPES, default='medical_certificate')
    purpose = models.CharField(max_length=200)
    additional_info = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    processed_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='processed_documents'
    )
    medical_certificate = models.ForeignKey(
        'health_forms_services.MedicalCertificate',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='document_requests',
        help_text='Linked medical certificate from Health Services'
    )
    rejection_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Document Request'
        verbose_name_plural = 'Document Requests'

    def __str__(self):
        name = f"{self.student.first_name} {self.student.last_name}".strip()
        if not name:
            name = self.student.email or self.student.username
        return f"{name} - {self.get_document_type_display()}"


# Backwards compatibility alias for existing code that uses CertificateRequest
CertificateRequest = DocumentRequest
