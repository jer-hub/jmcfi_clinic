from django.db import models
from django.conf import settings
from django.utils import timezone


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


class DentalHealthForm(models.Model):
    """Dental Records Form (F-HSS-20-0003) - matching the JMCFI Dental Records PDF.

    Comprehensive dental examination form with personal info, FDI dental chart,
    soft tissue exam, oral health condition, periodontal exam, tooth count,
    clinical data, and conditions/recommendations.
    """

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
        related_name='dental_health_forms'
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
        related_name='reviewed_dental_forms'
    )
    review_notes = models.TextField(blank=True)

    # ========== PERSONAL INFORMATION ==========
    last_name = models.CharField(max_length=100)
    first_name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, blank=True)
    age = models.PositiveIntegerField(blank=True, null=True)
    gender = models.CharField(max_length=10, choices=Gender.choices, blank=True)
    civil_status = models.CharField(max_length=20, choices=CivilStatus.choices, blank=True)
    address = models.TextField(blank=True)
    date_of_birth = models.DateField(blank=True, null=True)
    place_of_birth = models.CharField(max_length=200, blank=True)
    email_address = models.EmailField(blank=True)
    contact_number = models.CharField(max_length=20, blank=True)
    telephone_number = models.CharField(max_length=20, blank=True)
    designation = models.CharField(max_length=20, choices=Designation.choices, blank=True)
    department_college_office = models.CharField(max_length=200, blank=True)
    guardian_name = models.CharField(max_length=200, blank=True)
    guardian_contact = models.CharField(max_length=20, blank=True)
    date_of_examination = models.DateField(blank=True, null=True)

    # ========== INITIAL SOFT TISSUE EXAM ==========
    soft_tissue_lips = models.TextField(blank=True)
    soft_tissue_floor_of_mouth = models.TextField(blank=True)
    soft_tissue_palate = models.TextField(blank=True)
    soft_tissue_tongue = models.TextField(blank=True)
    soft_tissue_neck_nodes = models.TextField(blank=True)

    # ========== ORAL HEALTH CONDITION ==========
    oral_health_age_last_birthday = models.PositiveIntegerField(blank=True, null=True)
    presence_of_debris = models.BooleanField(default=False)
    inflammation_of_gingiva = models.BooleanField(default=False)
    presence_of_calculus = models.BooleanField(default=False)
    under_orthodontic_treatment = models.BooleanField(default=False)
    dentofacial_anomaly = models.TextField(blank=True, help_text='Dentofacial Anomaly, Neoplasm, Others')

    # ========== TOOTH COUNT ==========
    teeth_present = models.PositiveIntegerField(blank=True, null=True)
    caries_free_teeth = models.PositiveIntegerField(blank=True, null=True)
    decayed_teeth = models.PositiveIntegerField(blank=True, null=True)
    missing_teeth = models.PositiveIntegerField(blank=True, null=True)
    filled_teeth = models.PositiveIntegerField(blank=True, null=True)
    total_dmf_teeth = models.PositiveIntegerField(blank=True, null=True)

    # ========== INITIAL PERIODONTAL EXAM ==========
    class SeverityChoices(models.TextChoices):
        SLIGHT = 'slight', 'Slight'
        MODERATE = 'moderate', 'Moderate'
        SEVERE = 'severe', 'Severe'

    class BuildupChoices(models.TextChoices):
        LIGHT = 'light', 'Light'
        MODERATE = 'moderate', 'Moderate'
        HEAVY = 'heavy', 'Heavy'

    class EffectivenessChoices(models.TextChoices):
        GOOD = 'good', 'Good'
        FAIR = 'fair', 'Fair'
        POOR = 'poor', 'Poor'

    class PeriodontalDiagnosisChoices(models.TextChoices):
        NORMAL = 'normal', 'Normal'
        GINGIVITIS = 'gingivitis', 'Gingivitis'

    class PeriodontitisChoices(models.TextChoices):
        NONE = 'none', 'None'
        EARLY = 'early', 'Early'
        MODERATE = 'moderate', 'Moderate'
        ADVANCED = 'advanced', 'Advanced'

    class OcclusionChoices(models.TextChoices):
        CLASS_I = 'class_i', 'Class I'
        CLASS_II = 'class_ii', 'Class II'
        CLASS_III = 'class_iii', 'Class III'

    gingival_inflammation = models.CharField(max_length=20, choices=SeverityChoices.choices, blank=True)
    soft_plaque_buildup = models.CharField(max_length=20, choices=SeverityChoices.choices, blank=True)
    hard_calc_buildup = models.CharField(max_length=20, choices=BuildupChoices.choices, blank=True)
    stains = models.CharField(max_length=20, choices=BuildupChoices.choices, blank=True)
    home_care_effectiveness = models.CharField(max_length=20, choices=EffectivenessChoices.choices, blank=True)
    periodontal_condition = models.CharField(max_length=20, choices=EffectivenessChoices.choices, blank=True)
    periodontal_diagnosis = models.CharField(max_length=20, choices=PeriodontalDiagnosisChoices.choices, blank=True)
    periodontitis = models.CharField(max_length=20, choices=PeriodontitisChoices.choices, blank=True)
    mucogingival_defects = models.TextField(blank=True)

    # ========== CLINICAL DATA ==========
    occlusion = models.CharField(max_length=20, choices=OcclusionChoices.choices, blank=True)
    tmj_pain = models.BooleanField(default=False)
    tmj_popping = models.BooleanField(default=False)
    tmj_deviation = models.BooleanField(default=False)
    tmj_tooth_wear = models.BooleanField(default=False)

    # ========== CONDITIONS & RECOMMENDATIONS ==========
    cond_caries_free = models.BooleanField(default=False)
    cond_poor_oral_hygiene = models.BooleanField(default=False)
    cond_indicated_restoration = models.BooleanField(default=False)
    cond_indicated_extraction = models.BooleanField(default=False)
    cond_gingival_inflammation = models.BooleanField(default=False)
    cond_needs_oral_prophylaxis = models.BooleanField(default=False)
    cond_needs_prosthesis = models.BooleanField(default=False)
    cond_for_endodontic = models.BooleanField(default=False)
    cond_for_orthodontic = models.BooleanField(default=False)
    cond_for_sealant = models.BooleanField(default=False)
    cond_others = models.BooleanField(default=False)
    cond_others_detail = models.TextField(blank=True)
    cond_no_treatment_needed = models.BooleanField(default=False)

    # ========== REMARKS & DENTIST ==========
    remarks = models.TextField(blank=True)
    dentist_name = models.CharField(max_length=200, blank=True)
    dentist_license_no = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Dental Records Form'
        verbose_name_plural = 'Dental Records Forms'

    def __str__(self):
        name = f"{self.last_name}, {self.first_name}".strip(', ') or self.user.get_full_name()
        return f"Dental Records - {name} ({self.created_at.strftime('%Y-%m-%d')})"

    def get_full_name(self):
        """Return full name in Last, First Middle format"""
        parts = [self.last_name]
        if self.first_name:
            parts.append(self.first_name)
        if self.middle_name:
            parts.append(self.middle_name)
        return ', '.join(filter(None, parts[:2])) + (' ' + parts[2] if len(parts) > 2 else '')


class DentalFormTooth(models.Model):
    """Individual tooth record in FDI dental chart for DentalHealthForm"""
    TOOTH_TYPE_CHOICES = [
        ('permanent', 'Permanent'),
        ('primary', 'Primary/Deciduous'),
    ]

    CONDITION_CHOICES = [
        ('healthy', 'Healthy'),
        ('decayed', 'Decayed/Caries'),
        ('filled', 'Filled'),
        ('missing', 'Missing'),
        ('extracted', 'Extracted'),
        ('impacted', 'Impacted'),
        ('root_canal', 'Root Canal'),
        ('crowned', 'Crowned'),
        ('bridge', 'Bridge'),
        ('bridge_pontic', 'Bridge Pontic'),
        ('implant', 'Implant'),
        ('fractured', 'Fractured'),
        ('unerupted', 'Unerupted'),
        ('partially_erupted', 'Partially Erupted'),
        ('sealant', 'Sealant'),
        ('veneer', 'Veneer'),
        ('temporary', 'Temporary Filling'),
        ('root_fragment', 'Root Fragment'),
        ('anomaly', 'Anomaly'),
        ('other', 'Other'),
    ]

    dental_form = models.ForeignKey(DentalHealthForm, on_delete=models.CASCADE, related_name='dental_chart')
    tooth_number = models.PositiveIntegerField(
        help_text='FDI notation: 11-48 permanent, 51-85 primary'
    )
    tooth_type = models.CharField(max_length=20, choices=TOOTH_TYPE_CHOICES, default='permanent')
    condition = models.CharField(max_length=20, choices=CONDITION_CHOICES, default='healthy')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['tooth_number']
        unique_together = ['dental_form', 'tooth_number']

    def __str__(self):
        return f"Tooth #{self.tooth_number} - {self.get_condition_display()}"

    @property
    def fdi_quadrant(self):
        return self.tooth_number // 10

    @property
    def quadrant_name(self):
        names = {
            1: 'Upper Right', 2: 'Upper Left',
            3: 'Lower Left', 4: 'Lower Right',
            5: 'Upper Right (Primary)', 6: 'Upper Left (Primary)',
            7: 'Lower Left (Primary)', 8: 'Lower Right (Primary)',
        }
        return names.get(self.fdi_quadrant, 'Unknown')


class DentalFormToothSurface(models.Model):
    """Surface-level marking for individual tooth surfaces"""
    SURFACE_CHOICES = [
        ('mesial', 'Mesial (M)'),
        ('distal', 'Distal (D)'),
        ('buccal', 'Buccal/Facial (B/F)'),
        ('lingual', 'Lingual/Palatal (L/P)'),
        ('occlusal', 'Occlusal (O)'),
    ]

    SURFACE_CONDITION_CHOICES = [
        ('healthy', 'Healthy'),
        ('decayed', 'Decayed/Caries'),
        ('filled', 'Filled'),
        ('filled_with_caries', 'Filled with Caries'),
        ('sealant', 'Sealant'),
        ('fracture', 'Fracture'),
    ]

    tooth = models.ForeignKey(DentalFormTooth, on_delete=models.CASCADE, related_name='surfaces')
    surface = models.CharField(max_length=20, choices=SURFACE_CHOICES)
    condition = models.CharField(max_length=20, choices=SURFACE_CONDITION_CHOICES, default='healthy')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['tooth', 'surface']
        ordering = ['surface']

    def __str__(self):
        return f"Tooth #{self.tooth.tooth_number} - {self.get_surface_display()}"


class DentalServicesRequest(models.Model):
    """Dental Services Request Form — DENTAL FORM 2
    
    A checklist-based request form used by the dental clinic to record
    which dental services a patient needs. Categories: Periodontics,
    Operative Dentistry, Surgery, Prosthodontics, Endodontics, Pediatric.
    """

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending Review'
        COMPLETED = 'completed', 'Completed'
        REJECTED = 'rejected', 'Rejected'

    class Gender(models.TextChoices):
        MALE = 'male', 'Male'
        FEMALE = 'female', 'Female'

    # Form metadata
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='dental_services_requests'
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
        related_name='reviewed_dental_services'
    )
    review_notes = models.TextField(blank=True)

    # ========== PERSONAL INFORMATION ==========
    last_name = models.CharField(max_length=100)
    first_name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, blank=True)
    address = models.TextField(blank=True)
    age = models.PositiveIntegerField(blank=True, null=True)
    gender = models.CharField(max_length=10, choices=Gender.choices, blank=True)
    date_of_birth = models.DateField(blank=True, null=True)
    contact_number = models.CharField(max_length=20, blank=True)
    department = models.CharField(max_length=200, blank=True)

    # ========== PERIODONTICS ==========
    perio_oral_prophylaxis = models.BooleanField(default=False)
    perio_scaling_root_planning = models.BooleanField(default=False)

    # ========== OPERATIVE DENTISTRY ==========
    oper_class_i = models.BooleanField(default=False)
    oper_class_i_detail = models.CharField(max_length=300, blank=True)
    oper_class_ii = models.BooleanField(default=False)
    oper_class_ii_detail = models.CharField(max_length=300, blank=True)
    oper_class_iii = models.BooleanField(default=False)
    oper_class_iii_detail = models.CharField(max_length=300, blank=True)
    oper_class_iv = models.BooleanField(default=False)
    oper_class_iv_detail = models.CharField(max_length=300, blank=True)
    oper_class_v = models.BooleanField(default=False)
    oper_class_v_detail = models.CharField(max_length=300, blank=True)
    oper_class_vi = models.BooleanField(default=False)
    oper_class_vi_detail = models.CharField(max_length=300, blank=True)
    oper_onlay_inlay = models.BooleanField(default=False)
    oper_onlay_inlay_detail = models.CharField(max_length=300, blank=True)

    # ========== SURGERY ==========
    surg_tooth_extraction = models.BooleanField(default=False)
    surg_tooth_extraction_detail = models.CharField(max_length=300, blank=True)
    surg_odontectomy = models.BooleanField(default=False)
    surg_odontectomy_detail = models.CharField(max_length=300, blank=True)
    surg_operculectomy = models.BooleanField(default=False)
    surg_operculectomy_detail = models.CharField(max_length=300, blank=True)
    surg_other_pathological = models.BooleanField(default=False)
    surg_other_pathological_detail = models.CharField(max_length=300, blank=True)

    # ========== PROSTHODONTICS ==========
    prosth_complete_denture = models.BooleanField(default=False)
    prosth_rpd = models.BooleanField(default=False)
    prosth_rpd_detail = models.CharField(max_length=300, blank=True)
    prosth_fpd = models.BooleanField(default=False)
    prosth_fpd_detail = models.CharField(max_length=300, blank=True)
    prosth_single_crown = models.BooleanField(default=False)
    prosth_single_crown_detail = models.CharField(max_length=300, blank=True)
    prosth_veneers_laminates = models.BooleanField(default=False)
    prosth_veneers_laminates_detail = models.CharField(max_length=300, blank=True)

    # ========== ENDODONTICS ==========
    endo_anterior = models.BooleanField(default=False)
    endo_anterior_detail = models.CharField(max_length=300, blank=True)
    endo_posterior = models.BooleanField(default=False)
    endo_posterior_detail = models.CharField(max_length=300, blank=True)

    # ========== PEDIATRIC ==========
    pedo_fluoride = models.BooleanField(default=False)
    pedo_sealant = models.BooleanField(default=False)
    pedo_sealant_detail = models.CharField(max_length=300, blank=True)
    pedo_pulpotomy = models.BooleanField(default=False)
    pedo_pulpotomy_detail = models.CharField(max_length=300, blank=True)
    pedo_ssc = models.BooleanField(default=False)
    pedo_ssc_detail = models.CharField(max_length=300, blank=True)
    pedo_space_maintainer = models.BooleanField(default=False)
    pedo_space_maintainer_detail = models.CharField(max_length=300, blank=True)

    # ========== OTHER ==========
    currently_undergoing_treatment = models.BooleanField(default=False)
    currently_undergoing_treatment_detail = models.TextField(blank=True)

    # ========== DENTIST ==========
    dentist_name = models.CharField(max_length=200, blank=True)
    dentist_date = models.DateField(blank=True, null=True)
    dentist_license_no = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Dental Services Request'
        verbose_name_plural = 'Dental Services Requests'

    def __str__(self):
        name = f"{self.last_name}, {self.first_name}".strip(', ') or self.user.get_full_name()
        return f"Dental Services - {name} ({self.created_at.strftime('%Y-%m-%d')})"

    def get_full_name(self):
        """Return full name in Last, First Middle format"""
        parts = [self.last_name]
        if self.first_name:
            parts.append(self.first_name)
        if self.middle_name:
            parts.append(self.middle_name)
        return ', '.join(filter(None, parts[:2])) + (' ' + parts[2] if len(parts) > 2 else '')

    @property
    def selected_services(self):
        """Return list of selected service labels"""
        services = []
        service_map = {
            'perio_oral_prophylaxis': 'Oral Prophylaxis',
            'perio_scaling_root_planning': 'Scaling & Root Planning',
            'oper_class_i': 'Class I Restoration',
            'oper_class_ii': 'Class II Restoration',
            'oper_class_iii': 'Class III Restoration',
            'oper_class_iv': 'Class IV Restoration',
            'oper_class_v': 'Class V Restoration',
            'oper_class_vi': 'Class VI Restoration',
            'oper_onlay_inlay': 'Onlay / Inlay',
            'surg_tooth_extraction': 'Tooth Extraction',
            'surg_odontectomy': 'Odontectomy',
            'surg_operculectomy': 'Operculectomy',
            'surg_other_pathological': 'Other Pathological Case',
            'prosth_complete_denture': 'Complete Denture',
            'prosth_rpd': 'RPD',
            'prosth_fpd': 'FPD',
            'prosth_single_crown': 'Single Crown',
            'prosth_veneers_laminates': 'Veneers / Laminates',
            'endo_anterior': 'Endodontics (Anterior)',
            'endo_posterior': 'Endodontics (Posterior)',
            'pedo_fluoride': 'Fluoride',
            'pedo_sealant': 'Sealant',
            'pedo_pulpotomy': 'Pulpotomy',
            'pedo_ssc': 'SSC',
            'pedo_space_maintainer': 'Space Maintainer',
        }
        for field_name, label in service_map.items():
            if getattr(self, field_name, False):
                services.append(label)
        return services


class PatientChart(models.Model):
    """Patient Chart model - F-HSS-20-0002
    
    General medical consultation chart with patient demographics
    and a running log of consultation entries (date/time, findings, doctor's orders).
    """
    
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
        related_name='patient_charts'
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
        related_name='reviewed_patient_charts'
    )
    review_notes = models.TextField(blank=True)
    
    # ========== PERSONAL INFORMATION ==========
    last_name = models.CharField(max_length=100)
    first_name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, blank=True)
    address = models.TextField(blank=True)
    date_of_birth = models.DateField(blank=True, null=True)
    place_of_birth = models.CharField(max_length=200, blank=True)
    age = models.PositiveIntegerField(blank=True, null=True)
    gender = models.CharField(max_length=10, choices=Gender.choices, blank=True)
    civil_status = models.CharField(max_length=20, choices=CivilStatus.choices, blank=True)
    email_address = models.EmailField(blank=True)
    contact_number = models.CharField(max_length=20, blank=True)
    telephone_number = models.CharField(max_length=20, blank=True)
    designation = models.CharField(max_length=20, choices=Designation.choices, blank=True)
    department_college_office = models.CharField(max_length=200, blank=True)
    
    # Emergency Contact
    guardian_name = models.CharField(max_length=200, blank=True)
    guardian_contact = models.CharField(max_length=20, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Patient Chart'
        verbose_name_plural = 'Patient Charts'
    
    def __str__(self):
        name = f"{self.last_name}, {self.first_name}".strip(', ') or self.user.get_full_name()
        return f"Patient Chart - {name} ({self.created_at.strftime('%Y-%m-%d')})"
    
    def get_full_name(self):
        """Return full name in Last, First Middle format"""
        parts = [self.last_name]
        if self.first_name:
            parts.append(self.first_name)
        if self.middle_name:
            parts.append(self.middle_name)
        return ', '.join(filter(None, parts[:2])) + (' ' + parts[2] if len(parts) > 2 else '')


class PatientChartEntry(models.Model):
    """Individual consultation entry for a Patient Chart.
    
    Each row in the PDF's 'DATE AND TIME | FINDINGS | DOCTOR'S ORDERS' table.
    """
    patient_chart = models.ForeignKey(
        PatientChart,
        on_delete=models.CASCADE,
        related_name='entries'
    )
    date_and_time = models.DateTimeField(default=timezone.now)
    findings = models.TextField(blank=True)
    doctors_orders = models.TextField(blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='patient_chart_entries'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-date_and_time']
        verbose_name = 'Patient Chart Entry'
        verbose_name_plural = 'Patient Chart Entries'
    
    def __str__(self):
        return f"Entry {self.date_and_time.strftime('%Y-%m-%d %H:%M')} - {self.patient_chart}"


class Prescription(models.Model):
    """Prescription Form — F-HSS-20-0004
    
    A prescription pad used by the clinic physician to prescribe medications.
    Contains patient demographics and a list of prescription items.
    """

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending Review'
        COMPLETED = 'completed', 'Completed'
        REJECTED = 'rejected', 'Rejected'

    class Gender(models.TextChoices):
        MALE = 'male', 'Male'
        FEMALE = 'female', 'Female'

    # Form metadata
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='prescriptions'
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
        related_name='reviewed_prescriptions'
    )
    review_notes = models.TextField(blank=True)

    # ========== PATIENT INFORMATION ==========
    patient_name = models.CharField(max_length=200)
    age = models.PositiveIntegerField(blank=True, null=True)
    gender = models.CharField(max_length=10, choices=Gender.choices, blank=True)
    address = models.TextField(blank=True)
    date = models.DateField(blank=True, null=True, help_text='Date of prescription')

    # ========== PRESCRIPTION CONTENT ==========
    prescription_body = models.TextField(
        blank=True,
        help_text='Prescription details — medications, dosage, instructions'
    )

    # ========== PHYSICIAN INFORMATION ==========
    physician_name = models.CharField(max_length=200, blank=True)
    license_no = models.CharField(max_length=100, blank=True)
    ptr_no = models.CharField(max_length=100, blank=True, verbose_name='PTR No.')

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Prescription'
        verbose_name_plural = 'Prescriptions'

    def __str__(self):
        return f"Prescription - {self.patient_name} ({self.created_at.strftime('%Y-%m-%d')})"

    def get_full_name(self):
        return self.patient_name


class PrescriptionItem(models.Model):
    """Individual medication entry for a Prescription."""
    prescription = models.ForeignKey(
        Prescription,
        on_delete=models.CASCADE,
        related_name='items'
    )
    medication_name = models.CharField(max_length=300, help_text='Drug name / brand')
    dosage = models.CharField(max_length=200, blank=True, help_text='e.g. 500mg')
    frequency = models.CharField(max_length=200, blank=True, help_text='e.g. 3x a day')
    duration = models.CharField(max_length=200, blank=True, help_text='e.g. 7 days')
    quantity = models.CharField(max_length=100, blank=True, help_text='e.g. #21')
    instructions = models.TextField(blank=True, help_text='Special instructions')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['id']
        verbose_name = 'Prescription Item'
        verbose_name_plural = 'Prescription Items'

    def __str__(self):
        return f"{self.medication_name} — {self.prescription}"


class MedicalCertificate(models.Model):
    """Medical Certificate Form — F-HSS-20-0005
    
    Issued by the clinic physician certifying a patient's medical condition,
    diagnosis, and recommendations.
    """

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending Review'
        COMPLETED = 'completed', 'Completed'
        REJECTED = 'rejected', 'Rejected'

    class Gender(models.TextChoices):
        MALE = 'male', 'Male'
        FEMALE = 'female', 'Female'

    # Form metadata
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='medical_certificates'
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
        related_name='reviewed_medical_certificates'
    )
    review_notes = models.TextField(blank=True)

    # ========== CERTIFICATE INFORMATION ==========
    certificate_date = models.DateField(blank=True, null=True, help_text='Date printed on certificate')
    
    # ========== PATIENT INFORMATION ==========
    patient_name = models.CharField(max_length=200, help_text='Complete Name')
    age = models.PositiveIntegerField(blank=True, null=True)
    gender = models.CharField(max_length=10, choices=Gender.choices, blank=True)
    address = models.TextField(blank=True)
    consultation_date = models.DateField(blank=True, null=True, help_text='Date patient came in for consult')

    # ========== MEDICAL DETAILS ==========
    diagnosis = models.TextField(blank=True, help_text='Diagnosis / medical findings')
    remarks_recommendations = models.TextField(blank=True, help_text='Remarks and recommendations')

    # ========== PHYSICIAN INFORMATION ==========
    physician_name = models.CharField(max_length=200, blank=True)
    license_no = models.CharField(max_length=100, blank=True)
    ptr_no = models.CharField(max_length=100, blank=True, verbose_name='PTR No.')

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Medical Certificate'
        verbose_name_plural = 'Medical Certificates'

    def __str__(self):
        return f"Medical Certificate - {self.patient_name} ({self.created_at.strftime('%Y-%m-%d')})"

    def get_full_name(self):
        return self.patient_name
