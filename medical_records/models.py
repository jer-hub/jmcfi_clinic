from django.db import models
from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone

User = get_user_model()


def build_visit_snapshot(patient, doctor):
    """Capture patient/physician display fields at record creation time."""
    profile = getattr(patient, 'patient_profile', None)
    staff = getattr(doctor, 'staff_profile', None)
    email = (patient.email or '').strip()
    if profile and (profile.contact_email or '').strip():
        email = profile.contact_email.strip()
    return {
        'patient_name': patient.get_full_name() or email or '',
        'patient_id': (profile.patient_id if profile else '') or '',
        'email': email,
        'course': (profile.course if profile else '') or '',
        'department': (profile.department if profile else '') or '',
        'doctor_name': doctor.get_full_name() or doctor.email or '',
        'doctor_department': (staff.department if staff else '') or '',
        'doctor_specialization': (getattr(staff, 'specialization', '') if staff else '') or '',
    }


class MedicalRecord(models.Model):
    """Medical Record model for storing patient medical history and diagnoses."""

    STATUS_PENDING = 'pending'
    STATUS_COMPLETED = 'completed'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_COMPLETED, 'Completed'),
    ]

    patient = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='patient_medical_records',
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
    vital_signs = models.JSONField(default=dict, blank=True)  # Store BP, temperature, etc.
    lab_results = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        help_text=(
            'Pending only while the linked appointment is not yet confirmed. '
            'Completed when there is prescription or clinical documentation (vitals, labs, diagnosis/treatment).'
        ),
    )
    record_date = models.DateField(
        null=True,
        blank=True,
        help_text='Calendar date the clinical data was recorded (visit / entry date).',
    )
    visit_snapshot = models.JSONField(
        default=dict,
        blank=True,
        help_text='Patient and physician info frozen at record creation.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    _VITAL_SIGN_KEYS = (
        'blood_pressure',
        'temperature',
        'heart_rate',
        'pulse_rate',
        'respiratory_rate',
        'oxygen_saturation',
        'weight',
        'height',
    )

    @property
    def has_vital_signs_data(self):
        """True when at least one vital sign has a non-empty value."""
        if not self.vital_signs:
            return False
        for key in self._VITAL_SIGN_KEYS:
            value = self.vital_signs.get(key)
            if value is not None and str(value).strip():
                return True
        return False

    def has_prescription_data(self) -> bool:
        """True when a linked prescription has items or non-empty prescription body."""
        try:
            pr = self.prescription_record
        except ObjectDoesNotExist:
            return False
        if hasattr(pr, '_prefetched_objects_cache') and 'items' in pr._prefetched_objects_cache:
            if pr.items.all():
                return True
        else:
            if pr.items.exists():
                return True
        body = (pr.prescription_body or '').strip()
        return bool(body)

    def has_clinical_data(self) -> bool:
        """True when vitals, labs, or narrative diagnosis/treatment are present."""
        if (self.diagnosis or '').strip() and (self.treatment or '').strip():
            return True
        if self.has_vital_signs_data:
            return True
        if (self.lab_results or '').strip():
            return True
        return False

    @property
    def is_documentation_complete(self) -> bool:
        """Completed encounter documentation: prescription and/or clinical record content."""
        return self.has_prescription_data() or self.has_clinical_data()

    def appointment_status_value(self):
        """Appointment workflow status, or None for walk-ins."""
        if not self.appointment_id:
            return None
        if getattr(self, 'appointment', None) is not None:
            return self.appointment.status
        from appointments.models import Appointment

        return Appointment.objects.filter(pk=self.appointment_id).values_list('status', flat=True).first()

    def compute_status_value(self) -> str:
        """Derive stored status: pending only until appointment is confirmed; then completed if documented."""
        sid = self.appointment_status_value()
        if sid == 'pending':
            return self.STATUS_PENDING
        if self.is_documentation_complete:
            return self.STATUS_COMPLETED
        return self.STATUS_PENDING

    def timeline_filter_status(self, *, missed_slot: bool = False) -> str:
        """List stat-card bucket for mixed appointment/record timeline rows."""
        if missed_slot:
            return 'missed'
        if self.appointment_id:
            apt = self.appointment_status_value()
            if apt == 'pending':
                return 'pending'
            if apt == 'missed':
                return 'missed'
            if apt == 'cancelled':
                return 'cancelled'
            if self.is_documentation_complete:
                return 'completed'
            return apt
        return 'completed' if self.is_documentation_complete else 'pending'

    @property
    def effective_record_date(self):
        """Date shown as the record date (appointment day or created date)."""
        if self.record_date:
            return self.record_date
        created = self.created_at
        if timezone.is_aware(created):
            created = timezone.localtime(created)
        return created.date()

    def _snapshot_value(self, key):
        val = (self.visit_snapshot or {}).get(key)
        if val is not None and str(val).strip():
            return str(val).strip()
        return ''

    @property
    def display_patient_name(self):
        snap = self._snapshot_value('patient_name')
        return snap or self.patient.get_full_name()

    @property
    def display_patient_id(self):
        snap = self._snapshot_value('patient_id')
        if snap:
            return snap
        profile = getattr(self.patient, 'patient_profile', None)
        return profile.patient_id if profile else ''

    @property
    def display_patient_email(self):
        snap = self._snapshot_value('email')
        return snap or (self.patient.email or '')

    @property
    def display_patient_course(self):
        snap = self._snapshot_value('course')
        if snap:
            return snap
        profile = getattr(self.patient, 'patient_profile', None)
        return profile.course if profile else ''

    @property
    def display_patient_department(self):
        snap = self._snapshot_value('department')
        if snap:
            return snap
        profile = getattr(self.patient, 'patient_profile', None)
        return profile.department if profile else ''

    @property
    def display_doctor_name(self):
        snap = self._snapshot_value('doctor_name')
        return snap or self.doctor.get_full_name() or self.doctor.email or ''

    @property
    def display_doctor_department(self):
        snap = self._snapshot_value('doctor_department')
        if snap:
            return snap
        staff = getattr(self.doctor, 'staff_profile', None)
        return staff.department if staff else ''

    @property
    def display_doctor_specialization(self):
        snap = self._snapshot_value('doctor_specialization')
        if snap:
            return snap
        staff = getattr(self.doctor, 'staff_profile', None)
        return getattr(staff, 'specialization', '') if staff else ''

    def save(self, *args, **kwargs):
        if not self.visit_snapshot and self.patient_id and self.doctor_id:
            self.visit_snapshot = build_visit_snapshot(self.patient, self.doctor)
        if not self.record_date:
            if self.appointment_id:
                apt = getattr(self, 'appointment', None)
                if apt is None:
                    from appointments.models import Appointment
                    apt = Appointment.objects.filter(pk=self.appointment_id).only('date').first()
                if apt is not None:
                    self.record_date = apt.date
            if not self.record_date:
                self.record_date = timezone.localdate()
        self.status = self.compute_status_value()
        update_fields = kwargs.get('update_fields')
        if update_fields is not None:
            u = set(update_fields)
            u.update({'status', 'updated_at'})
            if self.record_date:
                u.add('record_date')
            if self.visit_snapshot:
                u.add('visit_snapshot')
            kwargs['update_fields'] = list(u)
        super().save(*args, **kwargs)

    def __str__(self):
        name = f"{self.patient.first_name} {self.patient.last_name}".strip()
        if not name:
            name = self.patient.email or self.patient.username
        return f"{name} - {self.effective_record_date}"
