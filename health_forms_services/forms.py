from django import forms
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from core.utils import clean_philippine_phone
from .models import HealthProfileForm, DentalHealthForm, DentalServicesRequest, PatientChart, PatientChartEntry, Prescription, PrescriptionItem

User = get_user_model()


class HealthProfilePersonalInfoForm(forms.ModelForm):
    """Form for editing personal information section"""
    
    class Meta:
        model = HealthProfileForm
        fields = [
            'last_name', 'first_name', 'middle_name',
            'permanent_address', 'zip_code', 'current_address',
            'religion', 'civil_status', 'place_of_birth',
            'date_of_birth', 'citizenship', 'age', 'gender',
            'email_address', 'mobile_number', 'telephone_number',
            'designation', 'department_college_office',
            'guardian_name', 'guardian_contact',
        ]
        widgets = {
            'last_name': forms.TextInput(attrs={'class': 'form-input'}),
            'first_name': forms.TextInput(attrs={'class': 'form-input'}),
            'middle_name': forms.TextInput(attrs={'class': 'form-input'}),
            'permanent_address': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 2}),
            'zip_code': forms.TextInput(attrs={'class': 'form-input'}),
            'current_address': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 2}),
            'religion': forms.TextInput(attrs={'class': 'form-input'}),
            'civil_status': forms.Select(attrs={'class': 'form-select'}),
            'place_of_birth': forms.TextInput(attrs={'class': 'form-input'}),
            'date_of_birth': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'citizenship': forms.TextInput(attrs={'class': 'form-input'}),
            'age': forms.NumberInput(attrs={'class': 'form-input'}),
            'gender': forms.Select(attrs={'class': 'form-select'}),
            'email_address': forms.EmailInput(attrs={'class': 'form-input'}),
            'mobile_number': forms.TextInput(attrs={
                'class': 'form-input pl-12 pr-10',
                'data-phone-input': 'true',
                'placeholder': '0917 123 4567',
                'inputmode': 'tel',
                'autocomplete': 'tel',
                'maxlength': '16',
            }),
            'telephone_number': forms.TextInput(attrs={'class': 'form-input'}),
            'designation': forms.Select(attrs={'class': 'form-select'}),
            'department_college_office': forms.TextInput(attrs={'class': 'form-input'}),
            'guardian_name': forms.TextInput(attrs={'class': 'form-input'}),
            'guardian_contact': forms.TextInput(attrs={
                'class': 'form-input pl-12 pr-10',
                'data-phone-input': 'true',
                'placeholder': '0917 123 4567',
                'inputmode': 'tel',
                'autocomplete': 'tel',
                'maxlength': '16',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Mark essential identifiers as required
        required_fields = [
            'last_name', 'first_name', 'date_of_birth', 'gender',
            'designation', 'department_college_office', 'mobile_number', 'email_address'
        ]
        for name in required_fields:
            if name in self.fields:
                self.fields[name].required = True

    def clean_mobile_number(self):
        return clean_philippine_phone(self.cleaned_data.get('mobile_number'))

    def clean_guardian_contact(self):
        return clean_philippine_phone(self.cleaned_data.get('guardian_contact'))


class HealthProfileMedicalHistoryForm(forms.ModelForm):
    """Form for editing medical history section"""
    
    class Meta:
        model = HealthProfileForm
        fields = [
            # Immunizations
            'immunization_covid19', 'immunization_covid19_date',
            'immunization_influenza', 'immunization_influenza_date',
            'immunization_pneumonia', 'immunization_pneumonia_date',
            'immunization_polio', 'immunization_polio_date',
            'immunization_hepatitis_b', 'immunization_hepatitis_b_date',
            'immunization_bcg', 'immunization_bcg_date',
            'immunization_dpt_tetanus', 'immunization_dpt_tetanus_date',
            'immunization_rotavirus', 'immunization_rotavirus_date',
            'immunization_hib', 'immunization_hib_date',
            'immunization_measles_mmr', 'immunization_measles_mmr_date',
            'immunization_others',
            # Illnesses
            'illness_measles', 'illness_mumps', 'illness_rubella',
            'illness_chickenpox', 'illness_ptb_pki', 'illness_hypertension',
            'illness_diabetes', 'illness_asthma', 'illness_others',
            # OB-GYN history (female)
            'menarche_age', 'menstrual_duration', 'menstrual_interval',
            'menstrual_amount', 'menstrual_symptoms', 'obstetric_history',
            # General medical info
            'allergies', 'current_medications', 'present_illness'
        ]
        widgets = {
            # Immunization checkboxes
            'immunization_covid19': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'immunization_covid19_date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'immunization_influenza': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'immunization_influenza_date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'immunization_pneumonia': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'immunization_pneumonia_date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'immunization_polio': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'immunization_polio_date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'immunization_hepatitis_b': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'immunization_hepatitis_b_date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'immunization_bcg': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'immunization_bcg_date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'immunization_dpt_tetanus': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'immunization_dpt_tetanus_date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'immunization_rotavirus': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'immunization_rotavirus_date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'immunization_hib': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'immunization_hib_date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'immunization_measles_mmr': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'immunization_measles_mmr_date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'immunization_others': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 2}),
            # Illness checkboxes
            'illness_measles': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'illness_mumps': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'illness_rubella': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'illness_chickenpox': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'illness_ptb_pki': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'illness_hypertension': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'illness_diabetes': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'illness_asthma': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'illness_others': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 2}),
            # OB-GYN
            'menarche_age': forms.NumberInput(attrs={'class': 'form-input', 'min': 0}),
            'menstrual_duration': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g., 3-5 days'}),
            'menstrual_interval': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g., every 28 days'}),
            'menstrual_amount': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'light / moderate / heavy'}),
            'menstrual_symptoms': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 2}),
            'obstetric_history': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 3}),
            # Medical info
            'allergies': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 3}),
            'current_medications': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 3}),
            'present_illness': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 4}),
        }

    def clean(self):
        cleaned = super().clean()
        # If an immunization checkbox is checked, require its date
        immunizations = [
            ('immunization_covid19', 'immunization_covid19_date'),
            ('immunization_influenza', 'immunization_influenza_date'),
            ('immunization_pneumonia', 'immunization_pneumonia_date'),
            ('immunization_polio', 'immunization_polio_date'),
            ('immunization_hepatitis_b', 'immunization_hepatitis_b_date'),
            ('immunization_bcg', 'immunization_bcg_date'),
            ('immunization_dpt_tetanus', 'immunization_dpt_tetanus_date'),
            ('immunization_rotavirus', 'immunization_rotavirus_date'),
            ('immunization_hib', 'immunization_hib_date'),
            ('immunization_measles_mmr', 'immunization_measles_mmr_date'),
        ]
        for flag, date_field in immunizations:
            if cleaned.get(flag) and not cleaned.get(date_field):
                self.add_error(date_field, 'Date is required when this vaccine is checked.')
        return cleaned


class HealthProfilePhysicalExamForm(forms.ModelForm):
    """Form for editing physical examination section"""
    
    class Meta:
        model = HealthProfileForm
        fields = [
            'blood_pressure', 'heart_rate', 'respiratory_rate',
            'temperature', 'spo2', 'height', 'weight',
            'bmi', 'bmi_remarks',
            'exam_general', 'exam_heent', 'exam_chest_lungs',
            'exam_abdomen', 'exam_genitourinary', 'exam_extremities',
            'exam_neurologic', 'exam_other_findings',
        ]
        widgets = {
            'blood_pressure': forms.TextInput(attrs={'class': 'form-input', 'placeholder': '120/80'}),
            'heart_rate': forms.NumberInput(attrs={'class': 'form-input', 'placeholder': 'bpm'}),
            'respiratory_rate': forms.NumberInput(attrs={'class': 'form-input', 'placeholder': '/min'}),
            'temperature': forms.NumberInput(attrs={'class': 'form-input', 'step': '0.1', 'placeholder': '°C'}),
            'spo2': forms.NumberInput(attrs={'class': 'form-input', 'step': '0.1', 'placeholder': '%'}),
            'height': forms.NumberInput(attrs={'class': 'form-input', 'step': '0.01', 'placeholder': 'meters'}),
            'weight': forms.NumberInput(attrs={'class': 'form-input', 'step': '0.1', 'placeholder': 'kg'}),
            'bmi': forms.NumberInput(attrs={'class': 'form-input', 'step': '0.01', 'readonly': True}),
            'bmi_remarks': forms.TextInput(attrs={'class': 'form-input', 'readonly': True}),
            'exam_general': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 2}),
            'exam_heent': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 2}),
            'exam_chest_lungs': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 2}),
            'exam_abdomen': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 2}),
            'exam_genitourinary': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 2}),
            'exam_extremities': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 2}),
            'exam_neurologic': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 2}),
            'exam_other_findings': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 3}),
        }


class HealthProfileClinicalSummaryForm(forms.ModelForm):
    """Form for editing clinical summary section"""
    
    class Meta:
        model = HealthProfileForm
        fields = [
            'physician_impression', 'final_remarks',
            'recommendations', 'examining_physician', 'examination_date',
        ]
        widgets = {
            'physician_impression': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 3}),
            'final_remarks': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 3}),
            'recommendations': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 3}),
            'examining_physician': forms.Select(attrs={'class': 'form-select'}),
            'examination_date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Populate examining_physician with doctor users
        doctors = User.objects.filter(role__in=['doctor', 'staff']).order_by('first_name', 'last_name')
        self.fields['examining_physician'].choices = [('', '---------')] + [
            (doctor.id, f"Dr. {doctor.get_full_name()}") for doctor in doctors
        ]


class HealthProfileDiagnosticTestsForm(forms.ModelForm):
    """Form for editing diagnostic tests section"""
    
    class Meta:
        model = HealthProfileForm
        fields = [
            'test_chest_xray', 'test_chest_xray_findings', 'test_chest_xray_date',
            'test_cbc', 'test_cbc_findings', 'test_cbc_date',
            'test_urinalysis', 'test_urinalysis_findings', 'test_urinalysis_date',
            'test_drug_test', 'test_drug_test_findings', 'test_drug_test_date',
            'test_psychological', 'test_psychological_findings', 'test_psychological_date',
            'test_hbsag', 'test_hbsag_findings', 'test_hbsag_date',
            'test_anti_hbs_titer', 'test_anti_hbs_titer_findings', 'test_anti_hbs_titer_date',
            'test_fecalysis', 'test_fecalysis_findings', 'test_fecalysis_date',
            'test_others',
        ]
        widgets = {
            # Chest X-ray
            'test_chest_xray': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'test_chest_xray_findings': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 2}),
            'test_chest_xray_date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            # CBC
            'test_cbc': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'test_cbc_findings': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 2}),
            'test_cbc_date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            # Urinalysis
            'test_urinalysis': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'test_urinalysis_findings': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 2}),
            'test_urinalysis_date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            # Drug Test
            'test_drug_test': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'test_drug_test_findings': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 2}),
            'test_drug_test_date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            # Psychological Test
            'test_psychological': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'test_psychological_findings': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 2}),
            'test_psychological_date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            # HBsAg
            'test_hbsag': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'test_hbsag_findings': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 2}),
            'test_hbsag_date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            # Anti-HBs Titer
            'test_anti_hbs_titer': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'test_anti_hbs_titer_findings': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 2}),
            'test_anti_hbs_titer_date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            # Fecalysis
            'test_fecalysis': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'test_fecalysis_findings': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 2}),
            'test_fecalysis_date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            # Others
            'test_others': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 3}),
        }

    def clean(self):
        cleaned = super().clean()
        tests = [
            ('test_chest_xray', 'test_chest_xray_date', 'test_chest_xray_findings'),
            ('test_cbc', 'test_cbc_date', 'test_cbc_findings'),
            ('test_urinalysis', 'test_urinalysis_date', 'test_urinalysis_findings'),
            ('test_drug_test', 'test_drug_test_date', 'test_drug_test_findings'),
            ('test_psychological', 'test_psychological_date', 'test_psychological_findings'),
            ('test_hbsag', 'test_hbsag_date', 'test_hbsag_findings'),
            ('test_anti_hbs_titer', 'test_anti_hbs_titer_date', 'test_anti_hbs_titer_findings'),
            ('test_fecalysis', 'test_fecalysis_date', 'test_fecalysis_findings'),
        ]
        for flag, date_field, find_field in tests:
            if cleaned.get(flag):
                if not cleaned.get(date_field):
                    self.add_error(date_field, 'Date is required when this test is checked.')
                if not cleaned.get(find_field):
                    self.add_error(find_field, 'Findings are required when this test is checked.')
        return cleaned


class HealthFormReviewForm(forms.ModelForm):
    """Form for staff/doctor to review and update form status"""
    
    class Meta:
        model = HealthProfileForm
        fields = ['status', 'review_notes']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-select'}),
            'review_notes': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 4}),
        }


# ========== DENTAL RECORDS FORM FORMS (F-HSS-20-0003) ==========

class DentalHealthPersonalInfoForm(forms.ModelForm):
    """Form for dental records form personal information"""

    class Meta:
        model = DentalHealthForm
        fields = [
            'last_name', 'first_name', 'middle_name',
            'age', 'gender', 'civil_status',
            'address', 'date_of_birth', 'place_of_birth',
            'email_address', 'contact_number', 'telephone_number',
            'designation', 'department_college_office',
            'guardian_name', 'guardian_contact',
            'date_of_examination',
        ]
        widgets = {
            'last_name': forms.TextInput(attrs={'class': 'form-input'}),
            'first_name': forms.TextInput(attrs={'class': 'form-input'}),
            'middle_name': forms.TextInput(attrs={'class': 'form-input'}),
            'age': forms.NumberInput(attrs={'class': 'form-input'}),
            'gender': forms.Select(attrs={'class': 'form-select'}),
            'civil_status': forms.Select(attrs={'class': 'form-select'}),
            'address': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 2}),
            'date_of_birth': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'place_of_birth': forms.TextInput(attrs={'class': 'form-input'}),
            'email_address': forms.EmailInput(attrs={'class': 'form-input'}),
            'contact_number': forms.TextInput(attrs={
                'class': 'form-input pl-12',
                'data-phone-input': 'true',
                'placeholder': '+639171234567 or 09171234567'
            }),
            'telephone_number': forms.TextInput(attrs={'class': 'form-input'}),
            'designation': forms.Select(attrs={'class': 'form-select'}),
            'department_college_office': forms.TextInput(attrs={'class': 'form-input'}),
            'guardian_name': forms.TextInput(attrs={'class': 'form-input'}),
            'guardian_contact': forms.TextInput(attrs={
                'class': 'form-input pl-12',
                'data-phone-input': 'true',
                'placeholder': '+639171234567 or 09171234567'
            }),
            'date_of_examination': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        required_fields = ['last_name', 'first_name']
        for name in required_fields:
            if name in self.fields:
                self.fields[name].required = True


class DentalHealthExaminationForm(forms.ModelForm):
    """Form for dental examination fields (soft tissue, oral health, periodontal, tooth count, clinical data)"""

    class Meta:
        model = DentalHealthForm
        fields = [
            # Soft Tissue Exam
            'soft_tissue_lips', 'soft_tissue_floor_of_mouth',
            'soft_tissue_palate', 'soft_tissue_tongue', 'soft_tissue_neck_nodes',
            # Oral Health Condition
            'oral_health_age_last_birthday', 'presence_of_debris',
            'inflammation_of_gingiva', 'presence_of_calculus',
            'under_orthodontic_treatment', 'dentofacial_anomaly',
            # Tooth Count
            'teeth_present', 'caries_free_teeth', 'decayed_teeth',
            'missing_teeth', 'filled_teeth', 'total_dmf_teeth',
            # Periodontal Exam
            'gingival_inflammation', 'soft_plaque_buildup', 'hard_calc_buildup',
            'stains', 'home_care_effectiveness', 'periodontal_condition',
            'periodontal_diagnosis', 'periodontitis', 'mucogingival_defects',
            # Clinical Data
            'occlusion', 'tmj_pain', 'tmj_popping',
            'tmj_deviation', 'tmj_tooth_wear',
        ]
        widgets = {
            # Soft Tissue
            'soft_tissue_lips': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 2, 'placeholder': 'Findings...'}),
            'soft_tissue_floor_of_mouth': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 2, 'placeholder': 'Findings...'}),
            'soft_tissue_palate': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 2, 'placeholder': 'Findings...'}),
            'soft_tissue_tongue': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 2, 'placeholder': 'Findings...'}),
            'soft_tissue_neck_nodes': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 2, 'placeholder': 'Findings...'}),
            # Oral Health
            'oral_health_age_last_birthday': forms.NumberInput(attrs={'class': 'form-input'}),
            'presence_of_debris': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'inflammation_of_gingiva': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'presence_of_calculus': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'under_orthodontic_treatment': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'dentofacial_anomaly': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 2, 'placeholder': 'Specify anomaly, neoplasm, or others...'}),
            # Tooth Count
            'teeth_present': forms.NumberInput(attrs={'class': 'form-input', 'min': 0}),
            'caries_free_teeth': forms.NumberInput(attrs={'class': 'form-input', 'min': 0}),
            'decayed_teeth': forms.NumberInput(attrs={'class': 'form-input', 'min': 0}),
            'missing_teeth': forms.NumberInput(attrs={'class': 'form-input', 'min': 0}),
            'filled_teeth': forms.NumberInput(attrs={'class': 'form-input', 'min': 0}),
            'total_dmf_teeth': forms.NumberInput(attrs={'class': 'form-input', 'min': 0}),
            # Periodontal
            'gingival_inflammation': forms.Select(attrs={'class': 'form-select'}),
            'soft_plaque_buildup': forms.Select(attrs={'class': 'form-select'}),
            'hard_calc_buildup': forms.Select(attrs={'class': 'form-select'}),
            'stains': forms.Select(attrs={'class': 'form-select'}),
            'home_care_effectiveness': forms.Select(attrs={'class': 'form-select'}),
            'periodontal_condition': forms.Select(attrs={'class': 'form-select'}),
            'periodontal_diagnosis': forms.Select(attrs={'class': 'form-select'}),
            'periodontitis': forms.Select(attrs={'class': 'form-select'}),
            'mucogingival_defects': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 2, 'placeholder': 'Describe defects...'}),
            # Clinical Data
            'occlusion': forms.Select(attrs={'class': 'form-select'}),
            'tmj_pain': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'tmj_popping': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'tmj_deviation': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'tmj_tooth_wear': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
        }


class DentalHealthConditionsForm(forms.ModelForm):
    """Form for conditions/recommendations, remarks, and dentist info"""

    class Meta:
        model = DentalHealthForm
        fields = [
            # Conditions & Recommendations
            'cond_caries_free', 'cond_poor_oral_hygiene',
            'cond_indicated_restoration', 'cond_indicated_extraction',
            'cond_gingival_inflammation', 'cond_needs_oral_prophylaxis',
            'cond_needs_prosthesis', 'cond_for_endodontic',
            'cond_for_orthodontic', 'cond_for_sealant',
            'cond_others', 'cond_others_detail',
            'cond_no_treatment_needed',
            # Remarks & Dentist
            'remarks', 'dentist_name', 'dentist_license_no',
        ]
        widgets = {
            'cond_caries_free': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'cond_poor_oral_hygiene': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'cond_indicated_restoration': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'cond_indicated_extraction': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'cond_gingival_inflammation': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'cond_needs_oral_prophylaxis': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'cond_needs_prosthesis': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'cond_for_endodontic': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'cond_for_orthodontic': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'cond_for_sealant': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'cond_others': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'cond_others_detail': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 2, 'placeholder': 'Specify other conditions...'}),
            'cond_no_treatment_needed': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'remarks': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 3, 'placeholder': 'Additional remarks...'}),
            'dentist_name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Signature over Printed Name'}),
            'dentist_license_no': forms.TextInput(attrs={'class': 'form-input'}),
        }


class DentalHealthFormReviewForm(forms.ModelForm):
    """Form for reviewing dental health forms"""

    class Meta:
        model = DentalHealthForm
        fields = ['status', 'review_notes']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-select'}),
            'review_notes': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 4}),
        }


# ========================================================================
# PATIENT CHART FORMS (F-HSS-20-0002)
# ========================================================================

class PatientChartPersonalInfoForm(forms.ModelForm):
    """Form for editing Patient Chart personal information section"""
    
    class Meta:
        model = PatientChart
        fields = [
            'last_name', 'first_name', 'middle_name',
            'address', 'date_of_birth', 'place_of_birth',
            'age', 'gender', 'civil_status',
            'email_address', 'contact_number', 'telephone_number',
            'designation', 'department_college_office',
            'guardian_name', 'guardian_contact',
        ]
        widgets = {
            'last_name': forms.TextInput(attrs={'class': 'form-input'}),
            'first_name': forms.TextInput(attrs={'class': 'form-input'}),
            'middle_name': forms.TextInput(attrs={'class': 'form-input'}),
            'address': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 2}),
            'date_of_birth': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'place_of_birth': forms.TextInput(attrs={'class': 'form-input'}),
            'age': forms.NumberInput(attrs={'class': 'form-input'}),
            'gender': forms.Select(attrs={'class': 'form-select'}),
            'civil_status': forms.Select(attrs={'class': 'form-select'}),
            'email_address': forms.EmailInput(attrs={'class': 'form-input'}),
            'contact_number': forms.TextInput(attrs={
                'class': 'form-input pl-12',
                'data-phone-input': 'true',
                'placeholder': '+639171234567 or 09171234567'
            }),
            'telephone_number': forms.TextInput(attrs={'class': 'form-input'}),
            'designation': forms.Select(attrs={'class': 'form-select'}),
            'department_college_office': forms.TextInput(attrs={'class': 'form-input'}),
            'guardian_name': forms.TextInput(attrs={'class': 'form-input'}),
            'guardian_contact': forms.TextInput(attrs={
                'class': 'form-input pl-12',
                'data-phone-input': 'true',
                'placeholder': '+639171234567 or 09171234567'
            }),
        }


class PatientChartEntryForm(forms.ModelForm):
    """Form for adding/editing consultation entries"""
    
    class Meta:
        model = PatientChartEntry
        fields = ['date_and_time', 'findings', 'doctors_orders']
        widgets = {
            'date_and_time': forms.DateTimeInput(attrs={
                'class': 'form-input',
                'type': 'datetime-local',
            }),
            'findings': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 3}),
            'doctors_orders': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 3}),
        }


class PatientChartReviewForm(forms.ModelForm):
    """Form for reviewing patient charts"""
    
    class Meta:
        model = PatientChart
        fields = ['status', 'review_notes']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-select'}),
            'review_notes': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 4}),
        }


# ========================================================================
# DENTAL SERVICES REQUEST FORMS (DENTAL FORM 2)
# ========================================================================

class DentalServicesPersonalInfoForm(forms.ModelForm):
    """Form for dental services request personal information"""

    class Meta:
        model = DentalServicesRequest
        fields = [
            'last_name', 'first_name', 'middle_name',
            'address', 'age', 'gender',
            'date_of_birth', 'contact_number', 'department',
        ]
        widgets = {
            'last_name': forms.TextInput(attrs={'class': 'form-input'}),
            'first_name': forms.TextInput(attrs={'class': 'form-input'}),
            'middle_name': forms.TextInput(attrs={'class': 'form-input'}),
            'address': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 2}),
            'age': forms.NumberInput(attrs={'class': 'form-input'}),
            'gender': forms.Select(attrs={'class': 'form-select'}),
            'date_of_birth': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'contact_number': forms.TextInput(attrs={
                'class': 'form-input pl-12',
                'data-phone-input': 'true',
                'placeholder': '+639171234567 or 09171234567'
            }),
            'department': forms.TextInput(attrs={'class': 'form-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ['last_name', 'first_name']:
            if name in self.fields:
                self.fields[name].required = True


class DentalServicesChecklistForm(forms.ModelForm):
    """Form for the services checklist (all service categories + dentist info)"""

    class Meta:
        model = DentalServicesRequest
        fields = [
            # Periodontics
            'perio_oral_prophylaxis', 'perio_scaling_root_planning',
            # Operative Dentistry
            'oper_class_i', 'oper_class_i_detail',
            'oper_class_ii', 'oper_class_ii_detail',
            'oper_class_iii', 'oper_class_iii_detail',
            'oper_class_iv', 'oper_class_iv_detail',
            'oper_class_v', 'oper_class_v_detail',
            'oper_class_vi', 'oper_class_vi_detail',
            'oper_onlay_inlay', 'oper_onlay_inlay_detail',
            # Surgery
            'surg_tooth_extraction', 'surg_tooth_extraction_detail',
            'surg_odontectomy', 'surg_odontectomy_detail',
            'surg_operculectomy', 'surg_operculectomy_detail',
            'surg_other_pathological', 'surg_other_pathological_detail',
            # Prosthodontics
            'prosth_complete_denture',
            'prosth_rpd', 'prosth_rpd_detail',
            'prosth_fpd', 'prosth_fpd_detail',
            'prosth_single_crown', 'prosth_single_crown_detail',
            'prosth_veneers_laminates', 'prosth_veneers_laminates_detail',
            # Endodontics
            'endo_anterior', 'endo_anterior_detail',
            'endo_posterior', 'endo_posterior_detail',
            # Pediatric
            'pedo_fluoride',
            'pedo_sealant', 'pedo_sealant_detail',
            'pedo_pulpotomy', 'pedo_pulpotomy_detail',
            'pedo_ssc', 'pedo_ssc_detail',
            'pedo_space_maintainer', 'pedo_space_maintainer_detail',
            # Other
            'currently_undergoing_treatment', 'currently_undergoing_treatment_detail',
            # Dentist
            'dentist_name', 'dentist_date', 'dentist_license_no',
        ]
        widgets = {
            # Periodontics
            'perio_oral_prophylaxis': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'perio_scaling_root_planning': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            # Operative Dentistry
            'oper_class_i': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'oper_class_i_detail': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Specify details...'}),
            'oper_class_ii': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'oper_class_ii_detail': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Specify details...'}),
            'oper_class_iii': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'oper_class_iii_detail': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Specify details...'}),
            'oper_class_iv': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'oper_class_iv_detail': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Specify details...'}),
            'oper_class_v': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'oper_class_v_detail': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Specify details...'}),
            'oper_class_vi': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'oper_class_vi_detail': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Specify details...'}),
            'oper_onlay_inlay': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'oper_onlay_inlay_detail': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Specify details...'}),
            # Surgery
            'surg_tooth_extraction': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'surg_tooth_extraction_detail': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Specify teeth/details...'}),
            'surg_odontectomy': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'surg_odontectomy_detail': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Specify details...'}),
            'surg_operculectomy': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'surg_operculectomy_detail': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Specify details...'}),
            'surg_other_pathological': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'surg_other_pathological_detail': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Specify case...'}),
            # Prosthodontics
            'prosth_complete_denture': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'prosth_rpd': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'prosth_rpd_detail': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Specify details...'}),
            'prosth_fpd': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'prosth_fpd_detail': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Specify details...'}),
            'prosth_single_crown': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'prosth_single_crown_detail': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Specify details...'}),
            'prosth_veneers_laminates': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'prosth_veneers_laminates_detail': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Specify details...'}),
            # Endodontics
            'endo_anterior': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'endo_anterior_detail': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Specify teeth...'}),
            'endo_posterior': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'endo_posterior_detail': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Specify teeth...'}),
            # Pediatric
            'pedo_fluoride': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'pedo_sealant': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'pedo_sealant_detail': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Specify details...'}),
            'pedo_pulpotomy': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'pedo_pulpotomy_detail': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Specify details...'}),
            'pedo_ssc': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'pedo_ssc_detail': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Specify details...'}),
            'pedo_space_maintainer': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'pedo_space_maintainer_detail': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Specify details...'}),
            # Other
            'currently_undergoing_treatment': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'currently_undergoing_treatment_detail': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 2, 'placeholder': 'Please specify current treatment...'}),
            # Dentist
            'dentist_name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Signature over Printed Name'}),
            'dentist_date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'dentist_license_no': forms.TextInput(attrs={'class': 'form-input'}),
        }


class DentalServicesReviewForm(forms.ModelForm):
    """Form for reviewing dental services requests"""

    class Meta:
        model = DentalServicesRequest
        fields = ['status', 'review_notes']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-select'}),
            'review_notes': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 4}),
        }


# ========================================================================
# PRESCRIPTION FORMS (F-HSS-20-0004)
# ========================================================================

class PrescriptionPatientForm(forms.ModelForm):
    """Form for prescription patient information and physician details"""

    class Meta:
        model = Prescription
        fields = [
            'patient_name', 'age', 'gender', 'address', 'date',
            'prescription_body',
            'physician_name', 'license_no', 'ptr_no',
        ]
        widgets = {
            'patient_name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Full name of the patient'}),
            'age': forms.NumberInput(attrs={'class': 'form-input'}),
            'gender': forms.Select(attrs={'class': 'form-select'}),
            'address': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 2}),
            'date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'prescription_body': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 6, 'placeholder': 'Enter prescription details here...'}),
            'physician_name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Signature over Printed Name'}),
            'license_no': forms.TextInput(attrs={'class': 'form-input'}),
            'ptr_no': forms.TextInput(attrs={'class': 'form-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['patient_name'].required = True


class PrescriptionItemForm(forms.ModelForm):
    """Form for individual prescription medication entries"""

    class Meta:
        model = PrescriptionItem
        fields = ['medication_name', 'dosage', 'frequency', 'duration', 'quantity', 'instructions']
        widgets = {
            'medication_name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Drug name / brand'}),
            'dosage': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. 500mg'}),
            'frequency': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. 3x a day'}),
            'duration': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. 7 days'}),
            'quantity': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. #21'}),
            'instructions': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 2, 'placeholder': 'Special instructions...'}),
        }


class PrescriptionReviewForm(forms.ModelForm):
    """Form for reviewing prescriptions"""

    class Meta:
        model = Prescription
        fields = ['status', 'review_notes']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-select'}),
            'review_notes': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 4}),
        }


