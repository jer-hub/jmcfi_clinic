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


# Import Appointment from appointments app for backwards compatibility
# The actual model is now in appointments.models
from appointments.models import Appointment, AppointmentTypeDefault

# Import MedicalRecord from medical_records app for backwards compatibility
# The actual model is now in medical_records.models
from medical_records.models import MedicalRecord

# Import CertificateRequest from document_request app for backwards compatibility
# The actual model is now in document_request.models as DocumentRequest
from document_request.models import DocumentRequest as CertificateRequest


# Health Tips Model - DEPRECATED: This model is kept for migration purposes only.
# The active HealthTip model is now in health_tips.models
# TODO: Create a data migration to move data from this model to health_tips.HealthTip
# and then remove this model in a future release.
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
        # Keep the original table name to maintain existing data
        db_table = 'management_healthtip'

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

# Feedback model has been moved to feedback app
# Import for backwards compatibility
from feedback.models import Feedback


# Note: Appointment and AppointmentTypeDefault models have been moved to appointments app
# They are imported at the top of this file for backwards compatibility
