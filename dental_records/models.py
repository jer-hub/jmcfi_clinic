from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator

User = get_user_model()


class DentalRecord(models.Model):
    """Main dental record for a patient"""
    CIVIL_STATUS_CHOICES = [
        ('single', 'Single'),
        ('married', 'Married'),
        ('widowed', 'Widowed'),
        ('separated', 'Separated'),
        ('divorced', 'Divorced'),
    ]
    
    DESIGNATION_CHOICES = [
        ('student', 'Student'),
        ('employee', 'Employee'),
    ]
    
    # Link to existing user
    patient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='dental_records')
    
    # Patient Demographics (some may duplicate user data but kept for completeness)
    middle_name = models.CharField(max_length=100, blank=True)
    age = models.PositiveIntegerField(null=True, blank=True)
    gender = models.CharField(max_length=10, choices=[('male', 'Male'), ('female', 'Female'), ('other', 'Other')])
    civil_status = models.CharField(max_length=20, choices=CIVIL_STATUS_CHOICES)
    address = models.TextField()
    date_of_birth = models.DateField()
    place_of_birth = models.CharField(max_length=200)
    email = models.EmailField()
    contact_number = models.CharField(max_length=20)
    telephone_number = models.CharField(max_length=20, blank=True)
    designation = models.CharField(max_length=20, choices=DESIGNATION_CHOICES)
    department_college_office = models.CharField(max_length=200)
    
    # Emergency Contact
    guardian_name = models.CharField(max_length=200)
    guardian_contact = models.CharField(max_length=20)
    
    # Examination Info
    date_of_examination = models.DateField(default=timezone.now)
    examined_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='dental_examinations')
    appointment = models.ForeignKey('appointments.Appointment', on_delete=models.SET_NULL, null=True, blank=True, related_name='dental_records')
    
    # Consent
    consent_signed = models.BooleanField(default=False)
    consent_date = models.DateField(null=True, blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-date_of_examination']
    
    def __str__(self):
        name = f"{self.patient.first_name} {self.middle_name} {self.patient.last_name}".strip()
        return f"Dental Record - {name} ({self.date_of_examination})"


class DentalExamination(models.Model):
    """Extraoral and Intraoral examination findings"""
    dental_record = models.OneToOneField(DentalRecord, on_delete=models.CASCADE, related_name='examination')
    
    # Extraoral Examination
    facial_symmetry = models.TextField(blank=True, help_text="Facial symmetry and profile assessment")
    cutaneous_areas = models.TextField(blank=True, help_text="Skin condition assessment")
    lips = models.TextField(blank=True, help_text="Lip assessment")
    eyes = models.TextField(blank=True, help_text="Eye assessment")
    lymph_nodes = models.TextField(blank=True, help_text="Lymph node assessment")
    tmj = models.TextField(blank=True, help_text="Temporomandibular joint assessment")
    
    # Intraoral Examination
    buccal_labial_mucosa = models.TextField(blank=True, help_text="Buccal and labial mucosa assessment")
    gingiva = models.TextField(blank=True, help_text="Gingiva assessment")
    palate_soft = models.TextField(blank=True, help_text="Soft palate assessment")
    palate_hard = models.TextField(blank=True, help_text="Hard palate assessment")
    tongue = models.TextField(blank=True, help_text="Tongue assessment")
    salivary_flow = models.TextField(blank=True, help_text="Salivary flow assessment")
    oral_hygiene = models.TextField(blank=True, help_text="Oral hygiene assessment")
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Examination for {self.dental_record}"


class DentalVitalSigns(models.Model):
    """Vital signs recorded during dental examination"""
    dental_record = models.OneToOneField(DentalRecord, on_delete=models.CASCADE, related_name='vital_signs')
    
    blood_pressure = models.CharField(max_length=20, blank=True, help_text="e.g., 120/80")
    pulse_rate = models.CharField(max_length=20, blank=True, help_text="beats per minute")
    respiratory_rate = models.CharField(max_length=20, blank=True, help_text="breaths per minute")
    temperature = models.CharField(max_length=20, blank=True, help_text="in Celsius or Fahrenheit")
    weight = models.CharField(max_length=20, blank=True, help_text="in kg or lbs")
    height = models.CharField(max_length=20, blank=True, help_text="in cm or ft")
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Vital Signs for {self.dental_record}"


class DentalHealthQuestionnaire(models.Model):
    """Health questionnaire (Section A) responses"""
    dental_record = models.OneToOneField(DentalRecord, on_delete=models.CASCADE, related_name='health_questionnaire')
    
    # General Health Questions
    last_hospital_date = models.DateField(null=True, blank=True)
    last_hospital_reason = models.TextField(blank=True)
    
    last_doctor_date = models.DateField(null=True, blank=True)
    last_doctor_reason = models.TextField(blank=True)
    
    doctor_care_2years = models.BooleanField(default=False, help_text="Under doctor's care last 2 years?")
    doctor_care_reason = models.TextField(blank=True)
    
    excessive_bleeding = models.BooleanField(default=False)
    excessive_bleeding_when = models.CharField(max_length=200, blank=True)
    
    medications_2years = models.BooleanField(default=False, help_text="Taking medicines last 2 years?")
    medications_for = models.TextField(blank=True)
    
    easily_exhausted = models.BooleanField(default=False, help_text="Easily exhausted when walking?")
    swollen_ankles = models.BooleanField(default=False, help_text="Swollen ankles during the day?")
    
    more_than_2_pillows = models.BooleanField(default=False, help_text="Use more than 2 pillows?")
    pillows_reason = models.TextField(blank=True)
    
    tumor_cancer = models.BooleanField(default=False, help_text="Diagnosis of tumor/cancer?")
    tumor_cancer_when = models.CharField(max_length=200, blank=True)
    
    # For Women Only
    is_pregnant = models.BooleanField(default=False)
    pregnancy_months = models.PositiveIntegerField(null=True, blank=True)
    
    birth_control_pills = models.BooleanField(default=False)
    birth_control_specify = models.CharField(max_length=200, blank=True)
    
    anticipate_pregnancy = models.BooleanField(default=False)
    having_period = models.BooleanField(default=False)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Health Questionnaire for {self.dental_record}"


class DentalSystemsReview(models.Model):
    """Systems review (Section B) - medical conditions checklist"""
    dental_record = models.OneToOneField(DentalRecord, on_delete=models.CASCADE, related_name='systems_review')
    
    # Cardiovascular
    heart_disease = models.BooleanField(default=False)
    hypertension = models.BooleanField(default=False)
    rheumatic_heart_disease = models.BooleanField(default=False)
    heart_surgery = models.BooleanField(default=False)
    stroke = models.BooleanField(default=False)
    
    # Respiratory
    asthma = models.BooleanField(default=False)
    emphysema = models.BooleanField(default=False)
    cough = models.BooleanField(default=False)
    pneumonia = models.BooleanField(default=False)
    hay_fever = models.BooleanField(default=False)
    sinus_problem = models.BooleanField(default=False)
    tuberculosis = models.BooleanField(default=False)
    
    # Blood/Hematologic
    anemia = models.BooleanField(default=False)
    bleeding_tendencies = models.BooleanField(default=False)
    hemophilia = models.BooleanField(default=False)
    sickle_cell_anemia = models.BooleanField(default=False)
    blood_transfusion = models.BooleanField(default=False)
    
    # Endocrine/Metabolic
    diabetes = models.BooleanField(default=False)
    thyroid_problem = models.BooleanField(default=False)
    glandular_problem = models.BooleanField(default=False)
    
    # Gastrointestinal
    stomach_ulcer = models.BooleanField(default=False)
    liver_problem = models.BooleanField(default=False)
    hepatitis_a = models.BooleanField(default=False)
    hepatitis_b = models.BooleanField(default=False)
    
    # Renal
    kidney_problem = models.BooleanField(default=False)
    
    # Infectious Diseases
    hiv_aids = models.BooleanField(default=False)
    scarlet_fever = models.BooleanField(default=False)
    std = models.BooleanField(default=False)
    
    # Neurological
    brain_injury = models.BooleanField(default=False)
    psychiatric_visit = models.BooleanField(default=False)
    
    # Musculoskeletal
    arthritis = models.BooleanField(default=False)
    rheumatism = models.BooleanField(default=False)
    tmj_problem = models.BooleanField(default=False)
    
    # Other Conditions
    cancer_treatment = models.BooleanField(default=False)
    allergies = models.TextField(blank=True, help_text="List any allergies")
    glaucoma = models.BooleanField(default=False)
    cold_sores = models.BooleanField(default=False)
    bruising = models.BooleanField(default=False)
    drug_addiction = models.BooleanField(default=False)
    ear_infection = models.BooleanField(default=False)
    hyperactivity = models.BooleanField(default=False)
    skin_disorder = models.BooleanField(default=False)
    development_problems = models.BooleanField(default=False)
    
    # Medications
    aspirin_medication = models.BooleanField(default=False)
    cortisone_medication = models.BooleanField(default=False)
    
    # Additional notes
    other_conditions = models.TextField(blank=True, help_text="Any other conditions not listed")
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Systems Review for {self.dental_record}"


class DentalHistory(models.Model):
    """Dental history (Section C) - dental-specific questions"""
    dental_record = models.OneToOneField(DentalRecord, on_delete=models.CASCADE, related_name='dental_history')
    
    # General Dental History
    first_dental_visit = models.BooleanField(default=False, help_text="Is this first dental visit?")
    last_dental_visit = models.DateField(null=True, blank=True)
    last_visit_reason = models.TextField(blank=True)
    
    teeth_extracted = models.BooleanField(default=False, help_text="Ever had teeth extracted?")
    extraction_when = models.CharField(max_length=200, blank=True)
    
    anesthesia_allergy = models.BooleanField(default=False, help_text="Allergy to local anesthesia?")
    anesthesia_allergy_when = models.CharField(max_length=200, blank=True)
    
    dental_appliance = models.BooleanField(default=False, help_text="Wearing dental appliance?")
    appliance_type = models.CharField(max_length=200, blank=True, help_text="e.g., braces, retainer, dentures")
    
    pain_discomfort = models.BooleanField(default=False, help_text="Pain or discomfort now?")
    pain_location = models.TextField(blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Dental History for {self.dental_record}"


class PediatricDentalHistory(models.Model):
    """Additional dental history for pediatric patients"""
    dental_record = models.OneToOneField(DentalRecord, on_delete=models.CASCADE, related_name='pediatric_history')
    
    child_mouth_condition = models.TextField(blank=True, help_text="Parent's assessment of child's mouth condition")
    normal_pregnancy_birth = models.BooleanField(default=True, help_text="Normal pregnancy and birth?")
    bottle_at_bedtime = models.BooleanField(default=False, help_text="Drinks milk from bottle at bedtime?")
    last_dentist_visit = models.DateField(null=True, blank=True)
    first_tooth_age_months = models.PositiveIntegerField(null=True, blank=True, help_text="Age in months when first tooth appeared")
    
    # Habits
    thumb_sucking = models.BooleanField(default=False)
    tongue_thrusting = models.BooleanField(default=False)
    nail_biting = models.BooleanField(default=False)
    mouth_breathing = models.BooleanField(default=False)
    teeth_grinding = models.BooleanField(default=False)
    other_habits = models.TextField(blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Pediatric History for {self.dental_record}"


class DentalChart(models.Model):
    """Individual tooth record in dental chart"""
    TOOTH_TYPE_CHOICES = [
        ('permanent', 'Permanent'),
        ('primary', 'Primary/Deciduous'),
    ]
    
    CONDITION_CHOICES = [
        ('healthy', 'Healthy'),
        ('cavity', 'Cavity/Caries'),
        ('filled', 'Filled'),
        ('missing', 'Missing'),
        ('extracted', 'Extracted'),
        ('impacted', 'Impacted'),
        ('root_canal', 'Root Canal'),
        ('crown', 'Crown'),
        ('bridge', 'Bridge'),
        ('implant', 'Implant'),
        ('fractured', 'Fractured'),
        ('other', 'Other'),
    ]
    
    dental_record = models.ForeignKey(DentalRecord, on_delete=models.CASCADE, related_name='dental_chart')
    
    tooth_number = models.PositiveIntegerField(help_text="Universal numbering: 1-32 for permanent, 51-85 for primary")
    tooth_type = models.CharField(max_length=20, choices=TOOTH_TYPE_CHOICES, default='permanent')
    condition = models.CharField(max_length=20, choices=CONDITION_CHOICES, default='healthy')
    notes = models.TextField(blank=True, help_text="Additional notes about this tooth")
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['tooth_number']
        unique_together = ['dental_record', 'tooth_number']
    
    def __str__(self):
        return f"Tooth #{self.tooth_number} - {self.get_condition_display()}"
