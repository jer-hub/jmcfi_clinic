from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator

User = get_user_model()

# Student Profile Model
class StudentProfile(models.Model):
    GENDER_CHOICES = [
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
    ]
    
    CIVIL_STATUS_CHOICES = [
        ('single', 'Single'),
        ('married', 'Married'),
        ('widowed', 'Widowed'),
        ('separated', 'Separated'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='student_profile')
    student_id = models.CharField(max_length=20, unique=True)
    profile_image = models.ImageField(upload_to='profiles/students/', blank=True, null=True, help_text="Profile photo")
    
    # Demographics
    middle_name = models.CharField(max_length=100, blank=True, default='')
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True, default='')
    civil_status = models.CharField(max_length=20, choices=CIVIL_STATUS_CHOICES, blank=True, default='')
    date_of_birth = models.DateField(null=True, blank=True)
    place_of_birth = models.CharField(max_length=200, blank=True, default='')
    age = models.IntegerField(null=True, blank=True)
    
    # Contact Information
    address = models.TextField(blank=True, default='')
    phone = models.CharField(max_length=20, blank=True, default='')
    telephone_number = models.CharField(max_length=20, blank=True, default='')
    emergency_contact = models.CharField(max_length=100, blank=True, default='')
    emergency_phone = models.CharField(max_length=20, blank=True, default='')
    
    # Institutional Information
    course = models.CharField(max_length=100, blank=True, default='')
    year_level = models.CharField(max_length=20, blank=True, default='')
    department = models.CharField(max_length=100, blank=True, default='')
    
    # Medical Information
    blood_type = models.CharField(max_length=5, choices=[
        ('A+', 'A+'), ('A-', 'A-'), ('B+', 'B+'), ('B-', 'B-'),
        ('AB+', 'AB+'), ('AB-', 'AB-'), ('O+', 'O+'), ('O-', 'O-')
    ], blank=True, null=True)
    allergies = models.TextField(blank=True, default='')
    medical_conditions = models.TextField(blank=True, default='')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        name = f"{self.user.first_name} {self.user.last_name}".strip()
        if not name:
            name = self.user.email or self.user.username
        return f"{name} - {self.student_id}"

    def get_profile_image_url(self):
        """Return profile image URL or None if no image"""
        if self.profile_image:
            return self.profile_image.url
        return None

# Staff Profile Model
class StaffProfile(models.Model):
    GENDER_CHOICES = [
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
    ]
    
    CIVIL_STATUS_CHOICES = [
        ('single', 'Single'),
        ('married', 'Married'),
        ('widowed', 'Widowed'),
        ('separated', 'Separated'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='staff_profile')
    staff_id = models.CharField(max_length=20, unique=True)
    profile_image = models.ImageField(upload_to='profiles/staff/', blank=True, null=True, help_text="Profile photo")
    
    # Demographics
    middle_name = models.CharField(max_length=100, blank=True, default='')
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True, default='')
    civil_status = models.CharField(max_length=20, choices=CIVIL_STATUS_CHOICES, blank=True, default='')
    date_of_birth = models.DateField(null=True, blank=True)
    place_of_birth = models.CharField(max_length=200, blank=True, default='')
    age = models.IntegerField(null=True, blank=True)
    
    # Contact Information
    address = models.TextField(blank=True, default='')
    phone = models.CharField(max_length=20, blank=True, default='')
    telephone_number = models.CharField(max_length=20, blank=True, default='')
    emergency_contact = models.CharField(max_length=100, blank=True, default='')
    emergency_phone = models.CharField(max_length=20, blank=True, default='')
    
    # Institutional Information
    department = models.CharField(max_length=100, blank=True, default='')
    position = models.CharField(max_length=100, blank=True, default='')
    specialization = models.CharField(max_length=100, blank=True)
    license_number = models.CharField(max_length=50, blank=True)
    
    # Medical Information
    blood_type = models.CharField(max_length=5, choices=[
        ('A+', 'A+'), ('A-', 'A-'), ('B+', 'B+'), ('B-', 'B-'),
        ('AB+', 'AB+'), ('AB-', 'AB-'), ('O+', 'O+'), ('O-', 'O-')
    ], blank=True, null=True)
    allergies = models.TextField(blank=True, default='')
    medical_conditions = models.TextField(blank=True, default='')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        name = f"{self.user.first_name} {self.user.last_name}".strip()
        if not name:
            name = self.user.email or self.user.username
        dept = self.department or 'No Department'
        return f"Dr. {name} - {dept}"

    def get_profile_image_url(self):
        """Return profile image URL or None if no image"""
        if self.profile_image:
            return self.profile_image.url
        return None

# Appointment Model
class Appointment(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    APPOINTMENT_TYPE_CHOICES = [
        ('consultation', 'General Consultation'),
        ('checkup', 'Health Checkup'),
        ('vaccination', 'Vaccination'),
        ('emergency', 'Emergency'),
        ('followup', 'Follow-up'),
    ]

    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='appointments')
    doctor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='doctor_appointments', limit_choices_to={'role__in': ['staff', 'doctor']})
    appointment_type = models.CharField(max_length=20, choices=APPOINTMENT_TYPE_CHOICES)
    date = models.DateField()
    time = models.TimeField()
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-time']

    def __str__(self):
        name = f"{self.student.first_name} {self.student.last_name}".strip()
        if not name:
            name = self.student.email or self.student.username
        return f"{name} - {self.date} {self.time}"

# Medical Record Model
class MedicalRecord(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='medical_records')
    doctor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_records')
    appointment = models.ForeignKey(Appointment, on_delete=models.CASCADE, null=True, blank=True)
    diagnosis = models.TextField()
    treatment = models.TextField()
    prescription = models.TextField(blank=True)
    vital_signs = models.JSONField(default=dict, blank=True)  # Store BP, temperature, etc.
    lab_results = models.TextField(blank=True)
    follow_up_required = models.BooleanField(default=False)
    follow_up_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        name = f"{self.student.first_name} {self.student.last_name}".strip()
        if not name:
            name = self.student.email or self.student.username
        return f"{name} - {self.created_at.date()}"

# Certificate Request Model
class CertificateRequest(models.Model):
    CERTIFICATE_TYPES = [
        ('fitness', 'Medical Fitness Certificate'),
        ('absence', 'Medical Leave Certificate'),
        ('vaccination', 'Vaccination Certificate'),
        ('health_record', 'Health Record Certificate'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('ready', 'Ready for Collection'),
    ]

    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='certificate_requests')
    certificate_type = models.CharField(max_length=20, choices=CERTIFICATE_TYPES)
    purpose = models.CharField(max_length=200)
    additional_info = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    processed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='processed_certificates')
    rejection_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        name = f"{self.student.first_name} {self.student.last_name}".strip()
        if not name:
            name = self.student.email or self.student.username
        return f"{name} - {self.get_certificate_type_display()}"

# Health Tips Model
class HealthTip(models.Model):
    CATEGORY_CHOICES = [
        ('nutrition', 'Nutrition'),
        ('exercise', 'Exercise'),
        ('mental_health', 'Mental Health'),
        ('hygiene', 'Hygiene'),
        ('prevention', 'Disease Prevention'),
        ('first_aid', 'First Aid'),
    ]

    title = models.CharField(max_length=200)
    content = models.TextField()
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='health_tips')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title

# Notification Model
class Notification(models.Model):
    TYPE_CHOICES = [
        ('appointment', 'Appointment Reminder'),
        ('certificate', 'Certificate Update'),
        ('health_tip', 'Health Tip'),
        ('general', 'General Notification'),
    ]
    
    TRANSACTION_TYPE_CHOICES = [
        # Appointment related
        ('appointment_reminder', 'Appointment Reminder'),
        ('appointment_confirmed', 'Appointment Confirmed'),
        ('appointment_cancelled', 'Appointment Cancelled'),
        ('appointment_completed', 'Appointment Completed'),
        ('appointment_scheduled', 'New Appointment Scheduled'),
        
        # Certificate related  
        ('certificate_requested', 'Certificate Request Submitted'),
        ('certificate_approved', 'Certificate Request Approved'),
        ('certificate_ready', 'Certificate Ready for Collection'),
        ('certificate_rejected', 'Certificate Request Rejected'),
        ('certificate_processing', 'Certificate Being Processed'),
        
        # Health tip related
        ('health_tip_new', 'New Health Tip Available'),
        ('health_tip_updated', 'Health Tip Updated'),
        
        # Medical record related
        ('medical_record_created', 'Medical Record Created'),
        ('medical_record_updated', 'Medical Record Updated'),
        
        # General system
        ('system_maintenance', 'System Maintenance'),
        ('general_announcement', 'General Announcement'),
        ('feedback_request', 'Feedback Request'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=200)
    message = models.TextField()
    notification_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    transaction_type = models.CharField(max_length=30, choices=TRANSACTION_TYPE_CHOICES, null=True, blank=True, help_text="Specific transaction type for better routing")
    related_id = models.PositiveIntegerField(null=True, blank=True, help_text="ID of the related object (appointment, certificate request, etc.)")
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        name = f"{self.user.first_name} {self.user.last_name}".strip()
        if not name:
            name = self.user.email or self.user.username
        return f"{name} - {self.title}"

# Feedback Model
class Feedback(models.Model):
    RATING_CHOICES = [
        (1, '1 - Poor'),
        (2, '2 - Fair'),
        (3, '3 - Good'),
        (4, '4 - Very Good'),
        (5, '5 - Excellent'),
    ]

    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='feedbacks')
    appointment = models.ForeignKey(Appointment, on_delete=models.CASCADE, null=True, blank=True)
    rating = models.IntegerField(choices=RATING_CHOICES, validators=[MinValueValidator(1), MaxValueValidator(5)])
    comments = models.TextField()
    suggestions = models.TextField(blank=True)
    is_anonymous = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        name = f"{self.student.first_name} {self.student.last_name}".strip()
        if not name:
            name = self.student.email or self.student.username
        return f"Feedback from {name} - {self.rating}/5"


# Appointment Type Default In-Charge Model
class AppointmentTypeDefault(models.Model):
    """
    Stores default in-charge doctor for each appointment type.
    Admin users can configure these defaults.
    """
    APPOINTMENT_TYPE_CHOICES = [
        ('consultation', 'General Consultation'),
        ('checkup', 'Health Checkup'),
        ('vaccination', 'Vaccination'),
        ('emergency', 'Emergency'),
        ('followup', 'Follow-up'),
    ]

    appointment_type = models.CharField(
        max_length=20, 
        choices=APPOINTMENT_TYPE_CHOICES, 
        unique=True,
        help_text="Type of appointment"
    )
    default_doctor = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='default_appointments',
        limit_choices_to={'role__in': ['staff', 'doctor']},
        help_text="Default in-charge doctor for this appointment type"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this default is active"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='appointment_type_updates',
        help_text="Admin user who last updated this setting"
    )

    class Meta:
        ordering = ['appointment_type']
        verbose_name = 'Appointment Type Default'
        verbose_name_plural = 'Appointment Type Defaults'

    def __str__(self):
        if self.default_doctor:
            doctor_name = f"{self.default_doctor.first_name} {self.default_doctor.last_name}".strip()
            if not doctor_name:
                doctor_name = self.default_doctor.email or self.default_doctor.username
            doctor_display = f"Dr. {doctor_name}"
        else:
            doctor_display = "Not Set"
        return f"{self.get_appointment_type_display()} → {doctor_display}"

    @classmethod
    def get_default_doctor(cls, appointment_type):
        """
        Get the default doctor for a specific appointment type.
        Returns None if no default is set or if the default is inactive.
        """
        try:
            default = cls.objects.get(
                appointment_type=appointment_type,
                is_active=True
            )
            return default.default_doctor
        except cls.DoesNotExist:
            return None
