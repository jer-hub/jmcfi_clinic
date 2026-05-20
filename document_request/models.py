from django.db import models

from django.contrib.auth import get_user_model

from django.db.models import Q

from django.utils import timezone



User = get_user_model()





class DocumentRequest(models.Model):

    """Model for certificate/document requests from students."""



    DOCUMENT_TYPES = [

        ('medical_certificate', 'Medical Certificate'),

        ('medical_record', 'Medical Record'),

        ('dental_record', 'Dental Record'),

    ]



    REQUEST_ORIGINS = [

        ('patient', 'Patient'),

        ('doctor', 'Doctor/Admin'),

    ]



    class Status(models.TextChoices):

        PENDING_REVIEW = 'pending_review', 'Pending review'

        COMPLETED = 'completed', 'Completed'

        REJECTED = 'rejected', 'Rejected'



    patient = models.ForeignKey(

        User,

        on_delete=models.CASCADE,

        related_name='document_requests',

    )

    created_by = models.ForeignKey(

        User,

        on_delete=models.SET_NULL,

        null=True,

        blank=True,

        related_name='created_document_requests',

        help_text='Who created the request (student self-request or doctor/admin on behalf).',

    )

    assigned_to = models.ForeignKey(

        User,

        on_delete=models.SET_NULL,

        null=True,

        blank=True,

        related_name='assigned_document_requests',

        limit_choices_to={'role__in': ['doctor', 'staff']},

        help_text='Primary clinician notified for this request.',

    )

    request_origin = models.CharField(max_length=20, choices=REQUEST_ORIGINS, default='patient')

    document_type = models.CharField(max_length=30, choices=DOCUMENT_TYPES, default='medical_certificate')

    purpose = models.CharField(max_length=200)

    additional_info = models.TextField(blank=True)

    status = models.CharField(

        max_length=20,

        choices=Status.choices,

        default=Status.PENDING_REVIEW,

    )

    processed_by = models.ForeignKey(

        User,

        on_delete=models.SET_NULL,

        null=True,

        blank=True,

        related_name='processed_documents',

    )

    medical_certificate = models.ForeignKey(

        'MedicalCertificate',

        on_delete=models.SET_NULL,

        null=True,

        blank=True,

        related_name='linked_document_requests',

        help_text='Linked medical certificate (legacy FK; prefer certificate.document_request).',

    )

    rejection_reason = models.TextField(blank=True)

    appointment = models.ForeignKey(
        'appointments.Appointment',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='document_requests',
        help_text='Completed visit this certificate request is tied to, when created from an appointment.',
    )

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)



    class Meta:

        ordering = ['-created_at']

        verbose_name = 'Document Request'

        verbose_name_plural = 'Document Requests'

        constraints = [
            models.UniqueConstraint(
                fields=['patient', 'document_type'],
                condition=Q(status='pending_review', appointment__isnull=True),
                name='uniq_pending_document_request_per_type',
            ),
            models.UniqueConstraint(
                fields=['patient', 'document_type', 'appointment'],
                condition=Q(status='pending_review') & ~Q(appointment__isnull=True),
                name='uniq_pending_document_request_per_appointment',
            ),
        ]



    def __str__(self):

        name = f"{self.patient.first_name} {self.patient.last_name}".strip()

        if not name:

            name = self.patient.email or self.patient.username

        return f"{name} - {self.get_document_type_display()}"



    @property

    def requires_medical_certificate(self):

        return self.document_type == 'medical_certificate'



    @property

    def is_pending_review(self):

        return self.status == self.Status.PENDING_REVIEW



    @property

    def is_completed(self):

        return self.status == self.Status.COMPLETED

    @property
    def is_ready_for_pickup(self):
        """Deprecated alias for :meth:`is_completed`."""
        return self.is_completed





# Backwards compatibility alias for existing code that uses CertificateRequest

CertificateRequest = DocumentRequest





class ClinicianSignature(models.Model):

    """Single active signature file per clinician for certificate signing."""



    doctor = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='clinician_signature',
        limit_choices_to={'role__in': ['doctor', 'staff', 'admin']},
    )

    signature_image = models.ImageField(upload_to='signatures/doctors/')

    is_active = models.BooleanField(default=True)

    updated_by = models.ForeignKey(

        User,

        on_delete=models.SET_NULL,

        null=True,

        blank=True,

        related_name='updated_clinician_signatures',

    )

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)



    class Meta:

        ordering = ['doctor__last_name', 'doctor__first_name']

        verbose_name = 'Clinician Signature'

        verbose_name_plural = 'Clinician Signatures'

        db_table = 'health_forms_services_doctorsignature'



    def __str__(self):

        return f"Signature - {self.doctor.get_full_name() or self.doctor.email}"





# Backwards compatibility: existing code imports DoctorSignature

DoctorSignature = ClinicianSignature





class MedicalCertificate(models.Model):

    """Medical certificate issued by clinic physician."""



    class Status(models.TextChoices):

        DRAFT = 'draft', 'Draft'

        ISSUED = 'issued', 'Issued'

        VOID = 'void', 'Void'



    class Gender(models.TextChoices):

        MALE = 'male', 'Male'

        FEMALE = 'female', 'Female'



    document_request = models.OneToOneField(

        DocumentRequest,

        on_delete=models.CASCADE,

        null=True,

        blank=True,

        related_name='certificate',

    )

    user = models.ForeignKey(

        User,

        on_delete=models.CASCADE,

        related_name='medical_certificates',

    )

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    reviewed_at = models.DateTimeField(blank=True, null=True)

    reviewed_by = models.ForeignKey(

        User,

        on_delete=models.SET_NULL,

        null=True,

        blank=True,

        related_name='reviewed_medical_certificates',

    )

    review_notes = models.TextField(blank=True)



    certificate_date = models.DateField(blank=True, null=True, help_text='Date printed on certificate')

    patient_name = models.CharField(max_length=200, help_text='Complete Name')

    age = models.PositiveIntegerField(blank=True, null=True)

    gender = models.CharField(max_length=10, choices=Gender.choices, blank=True)

    address = models.TextField(blank=True)

    consultation_date = models.DateField(blank=True, null=True, help_text='Date patient came in for consult')

    diagnosis = models.TextField(blank=True, help_text='Diagnosis / medical findings')

    remarks_recommendations = models.TextField(blank=True, help_text='Remarks and recommendations')

    physician_name = models.CharField(max_length=200, blank=True)

    license_no = models.CharField(max_length=100, blank=True)

    ptr_no = models.CharField(max_length=100, blank=True, verbose_name='PTR No.')



    signed_by = models.ForeignKey(

        User,

        on_delete=models.SET_NULL,

        null=True,

        blank=True,

        related_name='signed_medical_certificates',

    )

    signed_at = models.DateTimeField(blank=True, null=True)

    signature_snapshot = models.ImageField(upload_to='signatures/certificate_snapshots/', blank=True)

    signature_hash = models.CharField(max_length=64, blank=True)

    issued_pdf = models.FileField(upload_to='certificates/issued/', blank=True)



    class Meta:

        ordering = ['-created_at']

        verbose_name = 'Medical Certificate'

        verbose_name_plural = 'Medical Certificates'

        db_table = 'health_forms_services_medicalcertificate'



    def __str__(self):

        return f"Medical Certificate - {self.patient_name} ({self.created_at.strftime('%Y-%m-%d')})"



    def get_full_name(self):

        return self.patient_name



    @property

    def is_issued(self):

        return self.status == self.Status.ISSUED





class DocumentRequestEvent(models.Model):

    """Audit trail for document request workflow actions."""



    class EventType(models.TextChoices):

        CREATED = 'created', 'Created'

        CERTIFICATE_SAVED = 'certificate_saved', 'Certificate saved'

        APPROVED = 'approved', 'Approved'

        REJECTED = 'rejected', 'Rejected'



    request = models.ForeignKey(

        DocumentRequest,

        on_delete=models.CASCADE,

        related_name='events',

    )

    actor = models.ForeignKey(

        User,

        on_delete=models.SET_NULL,

        null=True,

        blank=True,

        related_name='document_request_events',

    )

    event_type = models.CharField(max_length=50, choices=EventType.choices)

    payload = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)



    class Meta:

        ordering = ['-created_at']

        verbose_name = 'Document Request Event'

        verbose_name_plural = 'Document Request Events'



    def __str__(self):

        return f"{self.request_id} — {self.event_type} @ {self.created_at}"


