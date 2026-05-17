from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.utils import timezone


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

    class ONBOARDING_STATUS(models.TextChoices):
        PENDING_ACTIVATION = 'pending_activation', 'Pending Activation'
        ACTIVE = 'active', 'Active'
        SUSPENDED = 'suspended', 'Suspended'
    
    role = models.CharField(
        max_length=10,
        choices=ROLE.choices,
        default=ROLE.STUDENT,)

    onboarding_status = models.CharField(
        max_length=20,
        choices=ONBOARDING_STATUS.choices,
        default=ONBOARDING_STATUS.ACTIVE,
    )
    
        # Re-add is_staff field (was removed in migration 0005, but Django requires it)
    is_staff = models.BooleanField(
        default=False,
        help_text='Designates whether the user can log into the admin site.',
    )

    # Soft-delete support
    is_deleted = models.BooleanField(
        default=False,
        help_text='Designates whether this user is soft-deleted.',
    )
    deleted_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Timestamp when the user was soft-deleted.',
    )

    # Last activity tracking for auto-cleanup
    last_activity_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Last activity timestamp for inactivity cleanup.',
    )
    
    def is_admin(self):
        return self.role == self.ROLE.ADMIN
    
    def is_doctor(self):
        return self.role == self.ROLE.DOCTOR
    
    def is_staff_member(self):
        return self.role == self.ROLE.STAFF
    
    def is_student(self):
        return self.role == self.ROLE.STUDENT

    def sync_onboarding_status(self):
        """Synchronize onboarding_status with is_active to keep them in sync."""
        if self.onboarding_status == self.ONBOARDING_STATUS.PENDING_ACTIVATION:
            if self.is_active:
                self.onboarding_status = self.ONBOARDING_STATUS.ACTIVE
        elif self.onboarding_status == self.ONBOARDING_STATUS.ACTIVE:
            if not self.is_active:
                self.onboarding_status = self.ONBOARDING_STATUS.SUSPENDED
        elif self.onboarding_status == self.ONBOARDING_STATUS.SUSPENDED:
            if self.is_active:
                self.onboarding_status = self.ONBOARDING_STATUS.ACTIVE

    def soft_delete(self):
        """Soft-delete the user instead of permanent deletion."""
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.is_active = False
        self.onboarding_status = self.ONBOARDING_STATUS.SUSPENDED
        self.save(update_fields=['is_deleted', 'deleted_at', 'is_active', 'onboarding_status'])

    def restore(self):
        """Restore a soft-deleted user."""
        self.is_deleted = False
        self.deleted_at = None
        self.is_active = True
        self.onboarding_status = self.ONBOARDING_STATUS.ACTIVE
        self.save(update_fields=['is_deleted', 'deleted_at', 'is_active', 'onboarding_status'])
    
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
        # Sync onboarding_status with is_active
        self.sync_onboarding_status()
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
    # Professional / Licensing (for staff/doctors)
    license_number = models.CharField(max_length=50, blank=True)
    ptr_no = models.CharField(max_length=100, blank=True, help_text='Professional Tax Receipt or PTR number')
    
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
    ptr_no = models.CharField(max_length=100, blank=True, help_text='Professional Tax Receipt or PTR number')
    
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


class CourseProgram(models.Model):
    college_department = models.ForeignKey(
        'CollegeDepartment',
        on_delete=models.PROTECT,
        related_name='course_programs',
    )
    name = models.CharField(max_length=120)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['college_department__name', 'name']
        unique_together = [('college_department', 'name')]

    def __str__(self):
        return f"{self.name} ({self.college_department.name})"


class CollegeDepartment(models.Model):
    name = models.CharField(max_length=120, unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class YearLevelOption(models.Model):
    college_department = models.ForeignKey(
        'CollegeDepartment',
        on_delete=models.PROTECT,
        related_name='year_levels',
    )
    name = models.CharField(max_length=50)
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['college_department__name', 'sort_order', 'name']
        unique_together = [('college_department', 'name')]

    def __str__(self):
        return f"{self.name} ({self.college_department.name})"


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
        ('direct_message', 'Direct Message'),
        ('announcement_posted', 'Announcement Posted'),
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

    def get_target_url(self):
        from django.urls import reverse

        from .utils import resolve_notification_url

        return resolve_notification_url(self) or reverse('core:notifications')


class UserInvite(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='invites')
    token_hash = models.CharField(max_length=64, unique=True, db_index=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_user_invites',
    )
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        status = 'accepted' if self.accepted_at else 'active'
        if self.revoked_at:
            status = 'revoked'
        return f"Invite<{self.user.email}> ({status})"


class AccountProvisioningAudit(models.Model):
    class ACTION(models.TextChoices):
        CREATED_PENDING = 'created_pending', 'Created (Pending Activation)'
        CREATED_ACTIVE = 'created_active', 'Created (Active)'
        ACTIVATED = 'activated', 'Activated'
        SUSPENDED = 'suspended', 'Suspended'
        SOFT_DELETED = 'soft_deleted', 'Soft Deleted'
        RESTORED = 'restored', 'Restored'
        BULK_ACTIVATED = 'bulk_activated', 'Bulk Activated'
        BULK_SUSPENDED = 'bulk_suspended', 'Bulk Suspended'
        ROLE_CHANGED = 'role_changed', 'Role Changed'
        PASSWORD_RESET = 'password_reset', 'Password Reset'

    actor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='provisioning_actions',
    )
    target_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='provisioning_audits',
    )
    action = models.CharField(max_length=30, choices=ACTION.choices)
    ip_address = models.CharField(max_length=45, blank=True, default='')
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        actor_email = self.actor.email if self.actor else 'system'
        return f"{actor_email} -> {self.target_user.email} [{self.action}]"


class ClinicSettings(models.Model):
    """Singleton clinic-wide configuration editable by admins."""

    SINGLETON_PK = 1

    clinic_name = models.CharField(max_length=120, default='JMCFI Clinic')
    logo = models.ImageField(upload_to='clinic/', blank=True, null=True)
    support_email = models.EmailField(blank=True, default='')
    support_phone = models.CharField(max_length=30, blank=True, default='')

    timezone = models.CharField(max_length=64, default='Asia/Manila')
    date_format = models.CharField(
        max_length=20,
        default='Y-m-d',
        help_text='Python strftime-style date format for exports and displays.',
    )

    google_allowed_domains = models.TextField(
        blank=True,
        default='',
        help_text='Comma-separated email domains allowed for Google sign-in. Empty uses env GOOGLE_ALLOWED_DOMAINS.',
    )
    allow_student_self_signup = models.BooleanField(
        default=True,
        help_text='Allow new students to register via Google OAuth.',
    )

    default_session_hours = models.PositiveSmallIntegerField(
        default=24,
        help_text='Fallback session length when role settings are unavailable.',
    )
    appointment_interval_minutes = models.PositiveSmallIntegerField(
        default=30,
        help_text='Minimum buffer between consecutive appointments.',
    )
    max_advance_booking_days = models.PositiveSmallIntegerField(
        default=30,
        help_text='How far ahead students may book appointments.',
    )
    cancellation_cutoff_hours = models.PositiveSmallIntegerField(
        default=24,
        help_text='Hours before appointment when cancellation is no longer allowed.',
    )

    enable_email_notifications = models.BooleanField(default=False)
    digest_hour = models.PositiveSmallIntegerField(
        default=8,
        help_text='Hour of day (0–23) for notification digests when enabled.',
    )

    maintenance_mode = models.BooleanField(default=False)
    maintenance_message = models.TextField(blank=True, default='')

    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='clinic_settings_updates',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Clinic settings'
        verbose_name_plural = 'Clinic settings'

    def save(self, *args, **kwargs):
        self.pk = self.SINGLETON_PK
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RuntimeError('Clinic settings cannot be deleted.')

    @classmethod
    def load(cls):
        """Return the singleton row, creating it with defaults if needed."""
        obj, _ = cls.objects.get_or_create(pk=cls.SINGLETON_PK)
        return obj

    def __str__(self):
        return self.clinic_name


class RoleSettings(models.Model):
    """Per-role defaults for sessions, profile policy, and feature access."""

    role = models.CharField(
        max_length=10,
        choices=User.ROLE.choices,
        unique=True,
    )
    session_timeout_seconds = models.PositiveIntegerField(
        help_text='Session expiry for this role, in seconds.',
    )
    profile_required_fields = models.JSONField(
        default=list,
        help_text='Field names required before profile is considered complete.',
    )

    can_access_analytics = models.BooleanField(default=True)
    can_submit_feedback = models.BooleanField(default=True)
    can_use_messaging = models.BooleanField(default=True)
    can_book_appointments = models.BooleanField(default=False)
    block_clinical_namespaces = models.BooleanField(
        default=False,
        help_text='When true, admin users cannot access clinical app namespaces.',
    )
    show_health_tips_nav = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Role settings'
        verbose_name_plural = 'Role settings'
        ordering = ['role']

    def __str__(self):
        return f'{self.get_role_display()} settings'


class UserPreferences(models.Model):
    """Per-user notification and UI preferences."""

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='preferences',
    )
    email_notifications = models.BooleanField(
        default=True,
        help_text='Receive email for important clinic updates.',
    )
    in_app_notifications = models.BooleanField(
        default=True,
        help_text='Show in-app notification alerts.',
    )
    compact_nav = models.BooleanField(
        default=False,
        help_text='Use a more compact navigation layout when supported.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'User preferences'
        verbose_name_plural = 'User preferences'

    def __str__(self):
        return f'Preferences for {self.user.email}'


class SettingsChangeLog(models.Model):
    """Audit trail for clinic and role settings changes."""

    class SettingType(models.TextChoices):
        CLINIC = 'clinic', 'Clinic'
        ROLE = 'role', 'Role'

    setting_type = models.CharField(max_length=10, choices=SettingType.choices)
    role = models.CharField(
        max_length=10,
        blank=True,
        default='',
        help_text='Role key when setting_type is role.',
    )
    field_name = models.CharField(max_length=80)
    old_value = models.TextField(blank=True, default='')
    new_value = models.TextField(blank=True, default='')
    changed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='settings_changes',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Settings change log'
        verbose_name_plural = 'Settings change logs'

    def __str__(self):
        target = self.role or self.get_setting_type_display()
        return f'{target}.{self.field_name} @ {self.created_at:%Y-%m-%d %H:%M}'

