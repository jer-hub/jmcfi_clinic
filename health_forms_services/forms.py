from django import forms
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from .models import HealthProfileForm

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
            'mobile_number': forms.TextInput(attrs={'class': 'form-input'}),
            'telephone_number': forms.TextInput(attrs={'class': 'form-input'}),
            'designation': forms.Select(attrs={'class': 'form-select'}),
            'department_college_office': forms.TextInput(attrs={'class': 'form-input'}),
            'guardian_name': forms.TextInput(attrs={'class': 'form-input'}),
            'guardian_contact': forms.TextInput(attrs={'class': 'form-input'}),
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
