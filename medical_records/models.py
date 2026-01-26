from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class MedicalRecord(models.Model):
    """Medical Record model for storing patient medical history and diagnoses."""
    
    student = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='patient_medical_records'
    )
    doctor = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='doctor_medical_records'
    )
    appointment = models.ForeignKey(
        'appointments.Appointment', 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True
    )
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
        db_table = 'management_medicalrecord'  # Keep existing table name

    def __str__(self):
        name = f"{self.student.first_name} {self.student.last_name}".strip()
        if not name:
            name = self.student.email or self.student.username
        return f"{name} - {self.created_at.date()}"
