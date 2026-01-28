from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager


class UserManager(BaseUserManager):
    """Custom user manager for email-based authentication"""
    
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', 'admin')

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)


# Create your models here.
class User(AbstractUser):
    # Override username to make it optional
    username = models.CharField(
        max_length=150,
        unique=True,
        blank=True,
        null=True,
        default=None,
        help_text='Optional. 150 characters or fewer. Letters, digits and @/./+/-/_ only.',
    )
    
    # Use email as the primary identifier
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []  # Remove username from required fields
    
    # Make email required and unique
    email = models.EmailField(unique=True)
    
    # Use custom manager
    objects = UserManager()
    
    class ROLE(models.TextChoices):
        ADMIN = 'admin', 'Admin'
        DOCTOR = 'doctor', 'Doctor'
        STAFF = 'staff', 'Staff'
        STUDENT = 'student', 'Student'
        # Add any additional fields you want for your user model
    
    role = models.CharField(
        max_length=10,
        choices=ROLE.choices,
        default=ROLE.STUDENT,)
    
    # Re-add is_staff field (was removed in migration 0005, but Django requires it)
    is_staff = models.BooleanField(
        default=False,
        help_text='Designates whether the user can log into the admin site.',
    )
    
    def is_admin(self):
        return self.role == self.ROLE.ADMIN
    
    def is_doctor(self):
        return self.role == self.ROLE.DOCTOR
    
    def is_staff_member(self):
        return self.role == self.ROLE.STAFF
    
    def is_student(self):
        return self.role == self.ROLE.STUDENT
    
    def __str__(self):
        if self.first_name or self.last_name:
            return f"{self.first_name} {self.last_name}".strip()
        return self.email or self.username or f"User {self.id}"
    
    def save(self, *args, **kwargs):
        # If is_staff is being set and role is not explicitly set, 
        # update role accordingly
        if hasattr(self, '_state') and self._state.adding and self.is_staff:
            if self.role == self.ROLE.STUDENT:
                self.role = self.ROLE.STAFF
        super().save(*args, **kwargs)


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

    class Meta:
        db_table = 'management_studentprofile'

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

    class Meta:
        db_table = 'management_staffprofile'

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
        db_table = 'management_notification'

    def __str__(self):
        name = f"{self.user.first_name} {self.user.last_name}".strip()
        if not name:
            name = self.user.email or self.user.username
        return f"{name} - {self.title}"
    
