from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class Appointment(models.Model):
    """Appointment model for scheduling student appointments with doctors."""
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    APPOINTMENT_TYPE_CHOICES = [
        ('consultation', 'General Consultation'),
        ('checkup', 'Health Checkup'),
        ('vaccination', 'Vaccination'),
        ('emergency', 'Emergency'),
        ('followup', 'Follow-up'),
        ('dental', 'Dental'),
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

    def __str__(self):
        name = f"{self.student.first_name} {self.student.last_name}".strip()
        if not name:
            name = self.student.email or self.student.username
        return f"{name} - {self.date} {self.time}"


class AppointmentTypeDefault(models.Model):
    """
    Stores assigned doctors for each appointment type.
    Admin users can configure which doctors are available per type.
    """
    APPOINTMENT_TYPE_CHOICES = [
        ('consultation', 'General Consultation'),
        ('checkup', 'Health Checkup'),
        ('vaccination', 'Vaccination'),
        ('emergency', 'Emergency'),
        ('followup', 'Follow-up'),
        ('dental', 'Dental'),
    ]

    appointment_type = models.CharField(
        max_length=20, 
        choices=APPOINTMENT_TYPE_CHOICES, 
        unique=True,
        help_text="Type of appointment"
    )
    assigned_doctors = models.ManyToManyField(
        User,
        blank=True,
        related_name='assigned_appointment_types',
        limit_choices_to={'role__in': ['staff', 'doctor']},
        help_text="Doctors allowed for this appointment type. If empty, all staff/doctors are available."
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

    def __str__(self):
        return self.get_appointment_type_display()
