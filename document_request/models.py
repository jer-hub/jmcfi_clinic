from django.db import models
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils import timezone

User = get_user_model()


class StudentRequestSchedule(models.Model):
    """Allowed schedule window for a student to submit record requests."""

    DAY_CHOICES = [
        ('mon', 'Monday'),
        ('tue', 'Tuesday'),
        ('wed', 'Wednesday'),
        ('thu', 'Thursday'),
        ('fri', 'Friday'),
        ('sat', 'Saturday'),
        ('sun', 'Sunday'),
    ]

    WEEKDAY_TO_CODE = {
        0: 'mon',
        1: 'tue',
        2: 'wed',
        3: 'thu',
        4: 'fri',
        5: 'sat',
        6: 'sun',
    }

    student = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='record_request_schedule',
        limit_choices_to={'role': 'student'},
    )
    allowed_days = models.JSONField(
        default=list,
        help_text='List of day codes (mon..sun) when requests are allowed.',
    )
    start_time = models.TimeField(help_text='Allowed request window start time.')
    end_time = models.TimeField(help_text='Allowed request window end time.')
    is_active = models.BooleanField(default=True)
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='updated_record_request_schedules',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['student__last_name', 'student__first_name']
        verbose_name = 'Student Request Schedule'
        verbose_name_plural = 'Student Request Schedules'

    def __str__(self):
        name = self.student.get_full_name() or self.student.email or self.student.username
        return f"{name} request schedule"

    def is_current_time_allowed(self, dt=None):
        """Return True when a datetime falls in this active schedule window."""
        if not self.is_active:
            return False

        current_dt = timezone.localtime(dt) if dt else timezone.localtime()
        day_code = self.WEEKDAY_TO_CODE[current_dt.weekday()]
        if day_code not in (self.allowed_days or []):
            return False

        current_time = current_dt.time().replace(second=0, microsecond=0)
        return self.start_time <= current_time <= self.end_time

    def get_allowed_days_display(self):
        labels = dict(self.DAY_CHOICES)
        return ', '.join(labels.get(day, day) for day in (self.allowed_days or []))

    def clean(self):
        super().clean()
        if self.start_time and self.end_time and self.start_time >= self.end_time:
            from django.core.exceptions import ValidationError
            raise ValidationError('Start time must be earlier than end time.')

        invalid_days = [d for d in (self.allowed_days or []) if d not in {c[0] for c in self.DAY_CHOICES}]
        if invalid_days:
            from django.core.exceptions import ValidationError
            raise ValidationError({'allowed_days': 'Allowed days contains invalid values.'})


class DocumentRequest(models.Model):
    """Model for certificate/document requests from students."""
    
    DOCUMENT_TYPES = [
        ('medical_certificate', 'Medical Certificate'),
        ('medical_record', 'Medical Record'),
        ('dental_record', 'Dental Record'),
    ]

    REQUEST_ORIGINS = [
        ('student', 'Student'),
        ('doctor', 'Doctor/Admin'),
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
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_document_requests',
        help_text='Who created the request (student self-request or doctor/admin on behalf).',
    )
    request_origin = models.CharField(max_length=20, choices=REQUEST_ORIGINS, default='student')
    document_type = models.CharField(max_length=30, choices=DOCUMENT_TYPES, default='medical_certificate')
    purpose = models.CharField(max_length=200)
    additional_info = models.TextField(blank=True)
    scheduled_for_date = models.DateField(null=True, blank=True)
    scheduled_for_time = models.TimeField(null=True, blank=True)
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
        constraints = [
            models.UniqueConstraint(
                fields=['student', 'document_type'],
                condition=Q(status='pending'),
                name='uniq_pending_document_request_per_type',
            )
        ]

    def __str__(self):
        name = f"{self.student.first_name} {self.student.last_name}".strip()
        if not name:
            name = self.student.email or self.student.username
        return f"{name} - {self.get_document_type_display()}"

    @property
    def requires_medical_certificate(self):
        return self.document_type == 'medical_certificate'


# Backwards compatibility alias for existing code that uses CertificateRequest
CertificateRequest = DocumentRequest
