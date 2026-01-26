from django import forms
from .models import HealthProfileForm


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


class HealthProfileMedicalHistoryForm(forms.ModelForm):
    """Form for editing medical history section"""
    
    class Meta:
        model = HealthProfileForm
        fields = ['allergies', 'current_medications', 'present_illness']
        widgets = {
            'allergies': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 3}),
            'current_medications': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 3}),
            'present_illness': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 4}),
        }


class HealthProfilePhysicalExamForm(forms.ModelForm):
    """Form for editing physical examination section"""
    
    class Meta:
        model = HealthProfileForm
        fields = [
            'blood_pressure', 'heart_rate', 'respiratory_rate',
            'temperature', 'spo2', 'height', 'weight',
            'bmi', 'bmi_remarks', 'other_findings',
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
            'other_findings': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 3}),
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
            'examining_physician': forms.TextInput(attrs={'class': 'form-input'}),
            'examination_date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
        }


class HealthFormReviewForm(forms.ModelForm):
    """Form for staff/doctor to review and update form status"""
    
    class Meta:
        model = HealthProfileForm
        fields = ['status', 'review_notes']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-select'}),
            'review_notes': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 4}),
        }
