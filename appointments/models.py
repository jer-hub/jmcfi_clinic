from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class Appointment(models.Model):
    """Appointment model for scheduling student appointments with doctors."""
    
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

    student = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='student_appointments'
    )
    doctor = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='assigned_appointments', 
        limit_choices_to={'role__in': ['staff', 'doctor']}
    )
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
        db_table = 'management_appointment'  # Keep existing table name

    def __str__(self):
        name = f"{self.student.first_name} {self.student.last_name}".strip()
        if not name:
            name = self.student.email or self.student.username
        return f"{name} - {self.date} {self.time}"


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
        related_name='appointment_type_defaults',
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
        related_name='appointment_type_setting_updates',
        help_text="Admin user who last updated this setting"
    )

    class Meta:
        ordering = ['appointment_type']
        verbose_name = 'Appointment Type Default'
        verbose_name_plural = 'Appointment Type Defaults'
        db_table = 'management_appointmenttypedefault'  # Keep existing table name

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
