from django.db import models
from django.conf import settings


class HealthProfileForm(models.Model):
    """Main Health Profile Form model - F-HSS-20-0001"""
    
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending Review'
        COMPLETED = 'completed', 'Completed'
        REJECTED = 'rejected', 'Rejected'
    
    class Designation(models.TextChoices):
        STUDENT = 'student', 'Student'
        EMPLOYEE = 'employee', 'Employee'
    
    class Gender(models.TextChoices):
        MALE = 'male', 'Male'
        FEMALE = 'female', 'Female'
    
    class CivilStatus(models.TextChoices):
        SINGLE = 'single', 'Single'
        MARRIED = 'married', 'Married'
        WIDOWED = 'widowed', 'Widowed'
        SEPARATED = 'separated', 'Separated'
    
    # Form metadata
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE,
        related_name='health_profile_forms'
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    reviewed_at = models.DateTimeField(blank=True, null=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_health_forms'
    )
    review_notes = models.TextField(blank=True)
    
    # ========== PERSONAL INFORMATION ==========
    last_name = models.CharField(max_length=100)
    first_name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, blank=True)
    permanent_address = models.TextField(blank=True)
    zip_code = models.CharField(max_length=10, blank=True)
    current_address = models.TextField(blank=True)
    religion = models.CharField(max_length=100, blank=True)
    civil_status = models.CharField(max_length=20, choices=CivilStatus.choices, blank=True)
    place_of_birth = models.CharField(max_length=200, blank=True)
    date_of_birth = models.DateField(blank=True, null=True)
    citizenship = models.CharField(max_length=100, blank=True)
    age = models.PositiveIntegerField(blank=True, null=True)
    gender = models.CharField(max_length=10, choices=Gender.choices, blank=True)
    email_address = models.EmailField(blank=True)
    mobile_number = models.CharField(max_length=20, blank=True)
    telephone_number = models.CharField(max_length=20, blank=True)
    designation = models.CharField(max_length=20, choices=Designation.choices, blank=True)
    department_college_office = models.CharField(max_length=200, blank=True)
    
    # Emergency Contact
    guardian_name = models.CharField(max_length=200, blank=True)
    guardian_contact = models.CharField(max_length=20, blank=True)
    
    # ========== MEDICAL HISTORY ==========
    # Immunization Records (Checkboxes)
    immunization_covid19 = models.BooleanField(default=False)
    immunization_covid19_date = models.DateField(blank=True, null=True)
    immunization_influenza = models.BooleanField(default=False)
    immunization_influenza_date = models.DateField(blank=True, null=True)
    immunization_pneumonia = models.BooleanField(default=False)
    immunization_pneumonia_date = models.DateField(blank=True, null=True)
    immunization_polio = models.BooleanField(default=False)
    immunization_polio_date = models.DateField(blank=True, null=True)
    immunization_hepatitis_b = models.BooleanField(default=False)
    immunization_hepatitis_b_date = models.DateField(blank=True, null=True)
    immunization_bcg = models.BooleanField(default=False)
    immunization_bcg_date = models.DateField(blank=True, null=True)
    immunization_dpt_tetanus = models.BooleanField(default=False)
    immunization_dpt_tetanus_date = models.DateField(blank=True, null=True)
    immunization_rotavirus = models.BooleanField(default=False)
    immunization_rotavirus_date = models.DateField(blank=True, null=True)
    immunization_hib = models.BooleanField(default=False)
    immunization_hib_date = models.DateField(blank=True, null=True)
    immunization_measles_mmr = models.BooleanField(default=False)
    immunization_measles_mmr_date = models.DateField(blank=True, null=True)
    immunization_others = models.TextField(blank=True, help_text="Other immunizations")
    
    # Illnesses/Medical Conditions (Checkboxes)
    illness_measles = models.BooleanField(default=False)
    illness_mumps = models.BooleanField(default=False)
    illness_rubella = models.BooleanField(default=False)
    illness_chickenpox = models.BooleanField(default=False)
    illness_ptb_pki = models.BooleanField(default=False)
    illness_hypertension = models.BooleanField(default=False)
    illness_diabetes = models.BooleanField(default=False)
    illness_asthma = models.BooleanField(default=False)
    illness_others = models.TextField(blank=True, help_text="Other illnesses/conditions")
    
    allergies = models.TextField(blank=True)
    current_medications = models.TextField(blank=True)
    
    # ========== OB-GYN HISTORY (Female) ==========
    menarche_age = models.PositiveIntegerField(blank=True, null=True)
    menstrual_duration = models.CharField(max_length=50, blank=True)
    menstrual_interval = models.CharField(max_length=50, blank=True)
    menstrual_amount = models.CharField(max_length=50, blank=True)
    menstrual_symptoms = models.TextField(blank=True)
    obstetric_history = models.TextField(blank=True)
    
    # ========== PRESENT ILLNESS ==========
    present_illness = models.TextField(blank=True)
    
    # ========== PHYSICAL EXAMINATION ==========
    # Vital Signs
    blood_pressure = models.CharField(max_length=20, blank=True)
    heart_rate = models.PositiveIntegerField(blank=True, null=True)
    respiratory_rate = models.PositiveIntegerField(blank=True, null=True)
    temperature = models.DecimalField(max_digits=4, decimal_places=1, blank=True, null=True)
    spo2 = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    
    # Anthropometrics
    height = models.DecimalField(max_digits=4, decimal_places=2, blank=True, null=True, 
                                  help_text="Height in meters")
    weight = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True,
                                  help_text="Weight in kg")
    bmi = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    bmi_remarks = models.CharField(max_length=50, blank=True)
    
    # Physical Exam Findings (Text Fields)
    exam_general = models.TextField(blank=True, help_text="General examination findings")
    exam_heent = models.TextField(blank=True, help_text="Head, Eyes, Ears, Nose, Throat findings")
    exam_chest_lungs = models.TextField(blank=True, help_text="Chest and lungs findings")
    exam_abdomen = models.TextField(blank=True, help_text="Abdomen findings")
    exam_genitourinary = models.TextField(blank=True, help_text="Genitourinary findings")
    exam_extremities = models.TextField(blank=True, help_text="Extremities findings")
    exam_neurologic = models.TextField(blank=True, help_text="Neurologic findings")
    exam_other_findings = models.TextField(blank=True, help_text="Other significant findings")
    
    # ========== DIAGNOSTIC TESTS ==========
    # Diagnostic Test Checkboxes
    test_chest_xray = models.BooleanField(default=False)
    test_chest_xray_findings = models.TextField(blank=True)
    test_chest_xray_date = models.DateField(blank=True, null=True)
    
    test_cbc = models.BooleanField(default=False)
    test_cbc_findings = models.TextField(blank=True)
    test_cbc_date = models.DateField(blank=True, null=True)
    
    test_urinalysis = models.BooleanField(default=False)
    test_urinalysis_findings = models.TextField(blank=True)
    test_urinalysis_date = models.DateField(blank=True, null=True)
    
    test_drug_test = models.BooleanField(default=False)
    test_drug_test_findings = models.TextField(blank=True)
    test_drug_test_date = models.DateField(blank=True, null=True)
    
    test_psychological = models.BooleanField(default=False)
    test_psychological_findings = models.TextField(blank=True)
    test_psychological_date = models.DateField(blank=True, null=True)
    
    test_hbsag = models.BooleanField(default=False)
    test_hbsag_findings = models.TextField(blank=True)
    test_hbsag_date = models.DateField(blank=True, null=True)
    
    test_anti_hbs_titer = models.BooleanField(default=False)
    test_anti_hbs_titer_findings = models.TextField(blank=True)
    test_anti_hbs_titer_date = models.DateField(blank=True, null=True)
    
    test_fecalysis = models.BooleanField(default=False)
    test_fecalysis_findings = models.TextField(blank=True)
    test_fecalysis_date = models.DateField(blank=True, null=True)
    
    test_others = models.TextField(blank=True, help_text="Other diagnostic tests")
    
    # ========== CLINICAL SUMMARY ==========
    physician_impression = models.TextField(blank=True)
    final_remarks = models.TextField(blank=True)
    recommendations = models.TextField(blank=True)
    examining_physician = models.ForeignKey(
        'core.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='examined_health_forms',
        limit_choices_to={'role__in': ['doctor', 'staff']}
    )
    examination_date = models.DateField(blank=True, null=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Health Profile Form'
        verbose_name_plural = 'Health Profile Forms'
    
    def __str__(self):
        name = f"{self.last_name}, {self.first_name}".strip(', ') or self.user.get_full_name()
        return f"Health Profile - {name} ({self.created_at.strftime('%Y-%m-%d')})"
    
    def calculate_bmi(self):
        """Calculate BMI from height and weight"""
        if self.height and self.weight and self.height > 0:
            bmi = float(self.weight) / (float(self.height) ** 2)
            self.bmi = round(bmi, 2)
            
            if bmi < 18.5:
                self.bmi_remarks = 'Underweight'
            elif 18.5 <= bmi < 25:
                self.bmi_remarks = 'Normal'
            elif 25 <= bmi < 30:
                self.bmi_remarks = 'Overweight'
            else:
                self.bmi_remarks = 'Obese'
            
            return self.bmi
        return None
    
    def get_full_name(self):
        """Return full name in Last, First Middle format"""
        parts = [self.last_name]
        if self.first_name:
            parts.append(self.first_name)
        if self.middle_name:
            parts.append(self.middle_name)
        return ', '.join(filter(None, parts[:2])) + (' ' + parts[2] if len(parts) > 2 else '')
