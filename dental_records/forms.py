"""
Dental Record Forms for Jose Maria College Foundation, Inc.
Forms for collecting comprehensive dental patient information
"""

from django import forms
from django.contrib.auth import get_user_model
from django.utils import timezone
from core.utils import clean_philippine_phone
from .models import (
    DentalRecord, DentalExamination, DentalVitalSigns,
    DentalHealthQuestionnaire, DentalSystemsReview,
    DentalHistory, PediatricDentalHistory, DentalChart,
    ProgressNote
)

User = get_user_model()


class DentalRecordForm(forms.ModelForm):
    """Main form for patient demographics"""
    
    # Custom patient search field
    patient_search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search patient by name, email, or ID...',
            'id': 'patient-search-input',
            'autocomplete': 'off'
        }),
        label='Search Patient'
    )
    
    # Student ID display field (read-only, auto-filled)
    student_id = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all bg-gray-50',
            'placeholder': 'Auto-filled from selected patient',
            'id': 'id_student_id',
            'readonly': 'readonly'
        }),
        label='Student/Staff ID'
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        today = timezone.now().date()
        # Set consent date defaults for new records
        if not self.instance.pk:
            self.fields['consent_date'].initial = today
            self.fields['informed_consent_date'].initial = today
            self.fields['consent_signed'].required = True
            self.fields['informed_consent_signed'].required = True
            self.fields['consent_signed'].widget.attrs['required'] = 'required'
            self.fields['informed_consent_signed'].widget.attrs['required'] = 'required'

    def clean(self):
        cleaned_data = super().clean()

        if not self.instance.pk:
            consent_signed = cleaned_data.get('consent_signed')
            informed_consent_signed = cleaned_data.get('informed_consent_signed')

            if not consent_signed:
                self.add_error('consent_signed', 'Patient consent is required before creating a dental record.')

            if not informed_consent_signed:
                self.add_error('informed_consent_signed', 'Informed consent is required before creating a dental record.')

            if consent_signed and not cleaned_data.get('consent_date'):
                cleaned_data['consent_date'] = timezone.now().date()

            if informed_consent_signed and not cleaned_data.get('informed_consent_date'):
                cleaned_data['informed_consent_date'] = timezone.now().date()

        return cleaned_data

    def clean_contact_number(self):
        return clean_philippine_phone(self.cleaned_data.get('contact_number'))

    def clean_guardian_contact(self):
        return clean_philippine_phone(self.cleaned_data.get('guardian_contact'))
    
    class Meta:
        model = DentalRecord
        fields = [
            'patient', 'middle_name', 'age', 'gender', 'civil_status',
            'address', 'date_of_birth', 'place_of_birth', 'email',
            'contact_number', 'telephone_number', 'designation',
            'department_college_office', 'guardian_name', 'guardian_contact',
            'date_of_examination', 'examined_by', 'appointment', 'consent_signed', 'consent_date',
            'informed_consent_signed', 'informed_consent_date'
        ]
        widgets = {
            'patient': forms.Select(attrs={
                'class': 'hidden',
                'id': 'patient-select-field'
            }),
            'middle_name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all',
                'placeholder': 'Middle Name'
            }),
            'age': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all',
                'min': '0',
                'max': '150'
            }),
            'gender': forms.Select(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all'
            }),
            'civil_status': forms.Select(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all'
            }),
            'address': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all',
                'rows': 3,
                'placeholder': 'Complete residential address'
            }),
            'date_of_birth': forms.DateInput(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all',
                'type': 'date'
            }),
            'place_of_birth': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all',
                'placeholder': 'City/Province'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all',
                'placeholder': 'email@example.com'
            }),
            'contact_number': forms.TextInput(attrs={
                'class': 'flex-1 min-w-0 px-3 pr-8 py-2.5 border-0 focus:outline-none focus:ring-0 bg-transparent',
                'placeholder': '917 123 4567',
                'data-phone-input': 'true',
                'data-phone-badge': 'true',
                'inputmode': 'tel',
                'autocomplete': 'tel',
                'maxlength': '16',
            }),
            'telephone_number': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all',
                'placeholder': 'Landline (optional)'
            }),
            'designation': forms.Select(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all'
            }),
            'department_college_office': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all',
                'placeholder': 'Department/College/Office'
            }),
            'guardian_name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all',
                'placeholder': 'Emergency Contact Name'
            }),
            'guardian_contact': forms.TextInput(attrs={
                'class': 'flex-1 min-w-0 px-3 pr-8 py-2.5 border-0 focus:outline-none focus:ring-0 bg-transparent',
                'placeholder': '917 123 4567',
                'data-phone-input': 'true',
                'data-phone-badge': 'true',
                'inputmode': 'tel',
                'autocomplete': 'tel',
                'maxlength': '16',
            }),
            'date_of_examination': forms.DateInput(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all',
                'type': 'date'
            }),
            'examined_by': forms.Select(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all'
            }),
            'appointment': forms.Select(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg bg-gray-50',
                'readonly': 'readonly'
            }),
            'consent_signed': forms.CheckboxInput(attrs={
                'class': 'w-4 h-4 text-primary-600 border-primary-300 rounded accent-primary-600'
            }),
            'consent_date': forms.DateInput(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg bg-gray-100 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all',
                'type': 'date',
                'readonly': 'readonly'
            }),
            'informed_consent_signed': forms.CheckboxInput(attrs={
                'class': 'w-4 h-4 text-primary-600 border-primary-300 rounded accent-primary-600'
            }),
            'informed_consent_date': forms.DateInput(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg bg-gray-100 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all',
                'type': 'date',
                'readonly': 'readonly'
            }),
        }
        labels = {
            'patient': 'Patient',
            'middle_name': 'Middle Name',
            'age': 'Age',
            'gender': 'Gender',
            'civil_status': 'Civil Status',
            'address': 'Complete Address',
            'date_of_birth': 'Date of Birth',
            'place_of_birth': 'Place of Birth',
            'email': 'Email Address',
            'contact_number': 'Mobile Number',
            'telephone_number': 'Telephone Number',
            'designation': 'Designation',
            'department_college_office': 'Department/College/Office',
            'guardian_name': 'Guardian/Emergency Contact Name',
            'guardian_contact': 'Guardian Contact Number',
            'date_of_examination': 'Date of Examination',
            'examined_by': 'Examined By (Dentist)',
            'consent_signed': 'Consent Form Signed',
            'consent_date': 'Consent Date',
            'informed_consent_signed': 'Informed Consent Signed',
            'informed_consent_date': 'Informed Consent Date',
        }


class StudentDentalIntakeForm(forms.ModelForm):
    """
    Stripped-down dental record form for student self-intake.
    Students fill in their own demographics and sign consent after a
    doctor confirms their dental appointment. Clinical fields (examined_by,
    appointment, date_of_examination) are handled by the view, not the student.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        today = timezone.now().date()
        self.fields['consent_date'].initial = today
        self.fields['informed_consent_date'].initial = today
        self.fields['consent_signed'].required = True
        self.fields['informed_consent_signed'].required = True

    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data.get('consent_signed'):
            self.add_error('consent_signed', 'You must give consent before submitting.')
        if not cleaned_data.get('informed_consent_signed'):
            self.add_error('informed_consent_signed', 'You must give informed consent before submitting.')
        if cleaned_data.get('consent_signed') and not cleaned_data.get('consent_date'):
            cleaned_data['consent_date'] = timezone.now().date()
        if cleaned_data.get('informed_consent_signed') and not cleaned_data.get('informed_consent_date'):
            cleaned_data['informed_consent_date'] = timezone.now().date()
        return cleaned_data

    def clean_contact_number(self):
        return clean_philippine_phone(self.cleaned_data.get('contact_number'))

    def clean_guardian_contact(self):
        return clean_philippine_phone(self.cleaned_data.get('guardian_contact'))

    class Meta:
        model = DentalRecord
        fields = [
            'middle_name', 'age', 'gender', 'civil_status',
            'address', 'date_of_birth', 'place_of_birth', 'email',
            'contact_number', 'telephone_number', 'designation',
            'department_college_office', 'guardian_name', 'guardian_contact',
            'consent_signed', 'consent_date',
            'informed_consent_signed', 'informed_consent_date',
        ]
        widgets = {
            'middle_name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all',
                'placeholder': 'Middle Name (optional)',
            }),
            'age': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all',
                'min': '0', 'max': '150',
            }),
            'gender': forms.Select(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all',
            }),
            'civil_status': forms.Select(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all',
            }),
            'address': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all',
                'rows': 3,
                'placeholder': 'Complete residential address',
            }),
            'date_of_birth': forms.DateInput(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all',
                'type': 'date',
            }),
            'place_of_birth': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all',
                'placeholder': 'City/Province',
            }),
            'email': forms.EmailInput(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all',
                'placeholder': 'email@example.com',
            }),
            'contact_number': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all',
                'placeholder': '09XX XXX XXXX',
                'inputmode': 'tel',
                'maxlength': '16',
            }),
            'telephone_number': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all',
                'placeholder': 'Landline (optional)',
            }),
            'designation': forms.Select(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all',
            }),
            'department_college_office': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all',
                'placeholder': 'Department / College / Office',
            }),
            'guardian_name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all',
                'placeholder': 'Emergency Contact Name',
            }),
            'guardian_contact': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all',
                'placeholder': '09XX XXX XXXX',
                'inputmode': 'tel',
                'maxlength': '16',
            }),
            'consent_signed': forms.CheckboxInput(attrs={
                'class': 'w-4 h-4 text-primary-600 border-primary-300 rounded accent-primary-600',
            }),
            'consent_date': forms.DateInput(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg bg-gray-100 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all',
                'type': 'date',
                'readonly': 'readonly',
            }),
            'informed_consent_signed': forms.CheckboxInput(attrs={
                'class': 'w-4 h-4 text-primary-600 border-primary-300 rounded accent-primary-600',
            }),
            'informed_consent_date': forms.DateInput(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg bg-gray-100 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all',
                'type': 'date',
                'readonly': 'readonly',
            }),
        }
        labels = {
            'middle_name': 'Middle Name',
            'age': 'Age',
            'gender': 'Gender',
            'civil_status': 'Civil Status',
            'address': 'Complete Address',
            'date_of_birth': 'Date of Birth',
            'place_of_birth': 'Place of Birth',
            'email': 'Email Address',
            'contact_number': 'Mobile Number',
            'telephone_number': 'Telephone Number (optional)',
            'designation': 'Designation',
            'department_college_office': 'Department / College / Office',
            'guardian_name': 'Emergency Contact Name',
            'guardian_contact': 'Emergency Contact Number',
            'consent_signed': 'I certify that all information provided is true and accurate.',
            'consent_date': 'Date',
            'informed_consent_signed': 'I authorize the dental clinic to perform necessary dental procedures.',
            'informed_consent_date': 'Date',
        }


class DentalExaminationForm(forms.ModelForm):
    """Form for extraoral and intraoral examination findings"""
    
    class Meta:
        model = DentalExamination
        fields = [
            'facial_symmetry', 'cutaneous_areas', 'lips', 'eyes', 'lymph_nodes', 'tmj',
            'buccal_labial_mucosa', 'gingiva', 'palate_soft', 'palate_hard',
            'tongue', 'salivary_flow', 'oral_hygiene'
        ]
        widgets = {
            'facial_symmetry': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all',
                'rows': 3
            }),
            'cutaneous_areas': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all',
                'rows': 3
            }),
            'lips': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all',
                'rows': 3
            }),
            'eyes': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all',
                'rows': 3
            }),
            'lymph_nodes': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all',
                'rows': 3
            }),
            'tmj': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all',
                'rows': 3
            }),
            'buccal_labial_mucosa': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all',
                'rows': 3
            }),
            'gingiva': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all',
                'rows': 3
            }),
            'palate_soft': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all',
                'rows': 3
            }),
            'palate_hard': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all',
                'rows': 3
            }),
            'tongue': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all',
                'rows': 3
            }),
            'salivary_flow': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all',
                'rows': 3
            }),
            'oral_hygiene': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all',
                'rows': 3
            }),
        }
        labels = {
            'facial_symmetry': 'Facial Symmetry & Profile',
            'cutaneous_areas': 'Cutaneous Areas',
            'lips': 'Lips',
            'eyes': 'Eyes',
            'lymph_nodes': 'Lymph Nodes',
            'tmj': 'TMJ (Temporomandibular Joint)',
            'buccal_labial_mucosa': 'Buccal & Labial Mucosa',
            'gingiva': 'Gingiva',
            'palate_soft': 'Soft Palate',
            'palate_hard': 'Hard Palate',
            'tongue': 'Tongue',
            'salivary_flow': 'Salivary Flow',
            'oral_hygiene': 'Oral Hygiene',
        }


class DentalVitalSignsForm(forms.ModelForm):
    """Form for recording vital signs"""
    
    class Meta:
        model = DentalVitalSigns
        fields = ['blood_pressure', 'pulse_rate', 'respiratory_rate', 'temperature', 'weight', 'height']
        widgets = {
            'blood_pressure': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all',
                'placeholder': 'e.g., 120/80'
            }),
            'pulse_rate': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all',
                'placeholder': 'bpm'
            }),
            'respiratory_rate': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all',
                'placeholder': 'breaths/min'
            }),
            'temperature': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all',
                'placeholder': '°C or °F'
            }),
            'weight': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all',
                'placeholder': 'kg or lbs'
            }),
            'height': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all',
                'placeholder': 'cm or ft'
            }),
        }
        labels = {
            'blood_pressure': 'Blood Pressure',
            'pulse_rate': 'Pulse Rate',
            'respiratory_rate': 'Respiratory Rate',
            'temperature': 'Temperature',
            'weight': 'Weight',
            'height': 'Height',
        }


class DentalHealthQuestionnaireForm(forms.ModelForm):
    """Form for health questionnaire (Section A)"""
    
    class Meta:
        model = DentalHealthQuestionnaire
        fields = [
            'last_hospital_date', 'last_hospital_reason',
            'last_doctor_date', 'last_doctor_reason',
            'doctor_care_2years', 'doctor_care_reason',
            'excessive_bleeding', 'excessive_bleeding_when',
            'medications_2years', 'medications_for',
            'easily_exhausted', 'swollen_ankles',
            'more_than_2_pillows', 'pillows_reason',
            'tumor_cancer', 'tumor_cancer_when',
            'is_pregnant', 'pregnancy_months',
            'birth_control_pills', 'birth_control_specify',
            'anticipate_pregnancy', 'having_period'
        ]
        widgets = {
            'last_hospital_date': forms.DateInput(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all',
                'type': 'date'
            }),
            'last_hospital_reason': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all',
                'rows': 3
            }),
            'last_doctor_date': forms.DateInput(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all',
                'type': 'date'
            }),
            'last_doctor_reason': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all',
                'rows': 3
            }),
            'doctor_care_2years': forms.CheckboxInput(attrs={
                'class': 'w-4 h-4 text-primary-600 border-primary-300 rounded accent-primary-600'
            }),
            'doctor_care_reason': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all',
                'rows': 3
            }),
            'excessive_bleeding': forms.CheckboxInput(attrs={
                'class': 'w-4 h-4 text-primary-600 border-primary-300 rounded accent-primary-600'
            }),
            'excessive_bleeding_when': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all'
            }),
            'medications_2years': forms.CheckboxInput(attrs={
                'class': 'w-4 h-4 text-primary-600 border-primary-300 rounded accent-primary-600'
            }),
            'medications_for': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all',
                'rows': 3
            }),
            'easily_exhausted': forms.CheckboxInput(attrs={
                'class': 'w-4 h-4 text-primary-600 border-primary-300 rounded accent-primary-600'
            }),
            'swollen_ankles': forms.CheckboxInput(attrs={
                'class': 'w-4 h-4 text-primary-600 border-primary-300 rounded accent-primary-600'
            }),
            'more_than_2_pillows': forms.CheckboxInput(attrs={
                'class': 'w-4 h-4 text-primary-600 border-primary-300 rounded accent-primary-600'
            }),
            'pillows_reason': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all',
                'rows': 3
            }),
            'tumor_cancer': forms.CheckboxInput(attrs={
                'class': 'w-4 h-4 text-primary-600 border-primary-300 rounded accent-primary-600'
            }),
            'tumor_cancer_when': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all'
            }),
            'is_pregnant': forms.CheckboxInput(attrs={
                'class': 'w-4 h-4 text-primary-600 border-primary-300 rounded accent-primary-600'
            }),
            'pregnancy_months': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all',
                'min': '0',
                'max': '9'
            }),
            'birth_control_pills': forms.CheckboxInput(attrs={
                'class': 'w-4 h-4 text-primary-600 border-primary-300 rounded accent-primary-600'
            }),
            'birth_control_specify': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all'
            }),
            'anticipate_pregnancy': forms.CheckboxInput(attrs={
                'class': 'w-4 h-4 text-primary-600 border-primary-300 rounded accent-primary-600'
            }),
            'having_period': forms.CheckboxInput(attrs={
                'class': 'w-4 h-4 text-primary-600 border-primary-300 rounded accent-primary-600'
            }),
        }


class DentalSystemsReviewForm(forms.ModelForm):
    """Form for systems review (Section B) - medical conditions checklist"""
    
    class Meta:
        model = DentalSystemsReview
        fields = [
            # Cardiovascular
            'heart_disease', 'hypertension', 'rheumatic_heart_disease', 'heart_surgery', 'stroke',
            # Respiratory
            'asthma', 'emphysema', 'cough', 'pneumonia', 'hay_fever', 'sinus_problem', 'tuberculosis',
            # Blood/Hematologic
            'anemia', 'bleeding_tendencies', 'hemophilia', 'sickle_cell_anemia', 'blood_transfusion',
            # Endocrine/Metabolic
            'diabetes', 'thyroid_problem', 'glandular_problem',
            # Gastrointestinal
            'stomach_ulcer', 'liver_problem', 'hepatitis_a', 'hepatitis_b',
            # Renal
            'kidney_problem',
            # Infectious Diseases
            'hiv_aids', 'scarlet_fever', 'std',
            # Neurological
            'brain_injury', 'psychiatric_visit',
            # Musculoskeletal
            'arthritis', 'rheumatism', 'tmj_problem',
            # Other Conditions
            'cancer_treatment', 'allergies', 'glaucoma', 'cold_sores', 'bruising',
            'drug_addiction', 'ear_infection', 'hyperactivity', 'skin_disorder', 'development_problems',
            # Medications
            'aspirin_medication', 'cortisone_medication',
            # Additional
            'other_conditions'
        ]
        widgets = {
            # All boolean fields as checkboxes
            'heart_disease': forms.CheckboxInput(attrs={'class': 'w-4 h-4 text-primary-600 border-primary-300 rounded accent-primary-600'}),
            'hypertension': forms.CheckboxInput(attrs={'class': 'w-4 h-4 text-primary-600 border-primary-300 rounded accent-primary-600'}),
            'rheumatic_heart_disease': forms.CheckboxInput(attrs={'class': 'w-4 h-4 text-primary-600 border-primary-300 rounded accent-primary-600'}),
            'heart_surgery': forms.CheckboxInput(attrs={'class': 'w-4 h-4 text-primary-600 border-primary-300 rounded accent-primary-600'}),
            'stroke': forms.CheckboxInput(attrs={'class': 'w-4 h-4 text-primary-600 border-primary-300 rounded accent-primary-600'}),
            'asthma': forms.CheckboxInput(attrs={'class': 'w-4 h-4 text-primary-600 border-primary-300 rounded accent-primary-600'}),
            'emphysema': forms.CheckboxInput(attrs={'class': 'w-4 h-4 text-primary-600 border-primary-300 rounded accent-primary-600'}),
            'cough': forms.CheckboxInput(attrs={'class': 'w-4 h-4 text-primary-600 border-primary-300 rounded accent-primary-600'}),
            'pneumonia': forms.CheckboxInput(attrs={'class': 'w-4 h-4 text-primary-600 border-primary-300 rounded accent-primary-600'}),
            'hay_fever': forms.CheckboxInput(attrs={'class': 'w-4 h-4 text-primary-600 border-primary-300 rounded accent-primary-600'}),
            'sinus_problem': forms.CheckboxInput(attrs={'class': 'w-4 h-4 text-primary-600 border-primary-300 rounded accent-primary-600'}),
            'tuberculosis': forms.CheckboxInput(attrs={'class': 'w-4 h-4 text-primary-600 border-primary-300 rounded accent-primary-600'}),
            'anemia': forms.CheckboxInput(attrs={'class': 'w-4 h-4 text-primary-600 border-primary-300 rounded accent-primary-600'}),
            'bleeding_tendencies': forms.CheckboxInput(attrs={'class': 'w-4 h-4 text-primary-600 border-primary-300 rounded accent-primary-600'}),
            'hemophilia': forms.CheckboxInput(attrs={'class': 'w-4 h-4 text-primary-600 border-primary-300 rounded accent-primary-600'}),
            'sickle_cell_anemia': forms.CheckboxInput(attrs={'class': 'w-4 h-4 text-primary-600 border-primary-300 rounded accent-primary-600'}),
            'blood_transfusion': forms.CheckboxInput(attrs={'class': 'w-4 h-4 text-primary-600 border-primary-300 rounded accent-primary-600'}),
            'diabetes': forms.CheckboxInput(attrs={'class': 'w-4 h-4 text-primary-600 border-primary-300 rounded accent-primary-600'}),
            'thyroid_problem': forms.CheckboxInput(attrs={'class': 'w-4 h-4 text-primary-600 border-primary-300 rounded accent-primary-600'}),
            'glandular_problem': forms.CheckboxInput(attrs={'class': 'w-4 h-4 text-primary-600 border-primary-300 rounded accent-primary-600'}),
            'stomach_ulcer': forms.CheckboxInput(attrs={'class': 'w-4 h-4 text-primary-600 border-primary-300 rounded accent-primary-600'}),
            'liver_problem': forms.CheckboxInput(attrs={'class': 'w-4 h-4 text-primary-600 border-primary-300 rounded accent-primary-600'}),
            'hepatitis_a': forms.CheckboxInput(attrs={'class': 'w-4 h-4 text-primary-600 border-primary-300 rounded accent-primary-600'}),
            'hepatitis_b': forms.CheckboxInput(attrs={'class': 'w-4 h-4 text-primary-600 border-primary-300 rounded accent-primary-600'}),
            'kidney_problem': forms.CheckboxInput(attrs={'class': 'w-4 h-4 text-primary-600 border-primary-300 rounded accent-primary-600'}),
            'hiv_aids': forms.CheckboxInput(attrs={'class': 'w-4 h-4 text-primary-600 border-primary-300 rounded accent-primary-600'}),
            'scarlet_fever': forms.CheckboxInput(attrs={'class': 'w-4 h-4 text-primary-600 border-primary-300 rounded accent-primary-600'}),
            'std': forms.CheckboxInput(attrs={'class': 'w-4 h-4 text-primary-600 border-primary-300 rounded accent-primary-600'}),
            'brain_injury': forms.CheckboxInput(attrs={'class': 'w-4 h-4 text-primary-600 border-primary-300 rounded accent-primary-600'}),
            'psychiatric_visit': forms.CheckboxInput(attrs={'class': 'w-4 h-4 text-primary-600 border-primary-300 rounded accent-primary-600'}),
            'arthritis': forms.CheckboxInput(attrs={'class': 'w-4 h-4 text-primary-600 border-primary-300 rounded accent-primary-600'}),
            'rheumatism': forms.CheckboxInput(attrs={'class': 'w-4 h-4 text-primary-600 border-primary-300 rounded accent-primary-600'}),
            'tmj_problem': forms.CheckboxInput(attrs={'class': 'w-4 h-4 text-primary-600 border-primary-300 rounded accent-primary-600'}),
            'cancer_treatment': forms.CheckboxInput(attrs={'class': 'w-4 h-4 text-primary-600 border-primary-300 rounded accent-primary-600'}),
            'glaucoma': forms.CheckboxInput(attrs={'class': 'w-4 h-4 text-primary-600 border-primary-300 rounded accent-primary-600'}),
            'cold_sores': forms.CheckboxInput(attrs={'class': 'w-4 h-4 text-primary-600 border-primary-300 rounded accent-primary-600'}),
            'bruising': forms.CheckboxInput(attrs={'class': 'w-4 h-4 text-primary-600 border-primary-300 rounded accent-primary-600'}),
            'drug_addiction': forms.CheckboxInput(attrs={'class': 'w-4 h-4 text-primary-600 border-primary-300 rounded accent-primary-600'}),
            'ear_infection': forms.CheckboxInput(attrs={'class': 'w-4 h-4 text-primary-600 border-primary-300 rounded accent-primary-600'}),
            'hyperactivity': forms.CheckboxInput(attrs={'class': 'w-4 h-4 text-primary-600 border-primary-300 rounded accent-primary-600'}),
            'skin_disorder': forms.CheckboxInput(attrs={'class': 'w-4 h-4 text-primary-600 border-primary-300 rounded accent-primary-600'}),
            'development_problems': forms.CheckboxInput(attrs={'class': 'w-4 h-4 text-primary-600 border-primary-300 rounded accent-primary-600'}),
            'aspirin_medication': forms.CheckboxInput(attrs={'class': 'w-4 h-4 text-primary-600 border-primary-300 rounded accent-primary-600'}),
            'cortisone_medication': forms.CheckboxInput(attrs={'class': 'w-4 h-4 text-primary-600 border-primary-300 rounded accent-primary-600'}),
            'allergies': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all',
                'rows': 3,
                'placeholder': 'List any allergies'
            }),
            'other_conditions': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all',
                'rows': 3,
                'placeholder': 'Any other conditions'
            }),
        }


class DentalHistoryForm(forms.ModelForm):
    """Form for dental history (Section C)"""
    
    class Meta:
        model = DentalHistory
        fields = [
            'first_dental_visit', 'last_dental_visit', 'last_visit_reason',
            'teeth_extracted', 'extraction_when',
            'anesthesia_allergy', 'anesthesia_allergy_when',
            'dental_appliance', 'appliance_type',
            'pain_discomfort', 'pain_location'
        ]
        widgets = {
            'first_dental_visit': forms.CheckboxInput(attrs={
                'class': 'w-4 h-4 text-primary-600 border-primary-300 rounded accent-primary-600'
            }),
            'last_dental_visit': forms.DateInput(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all',
                'type': 'date'
            }),
            'last_visit_reason': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all',
                'rows': 3
            }),
            'teeth_extracted': forms.CheckboxInput(attrs={
                'class': 'w-4 h-4 text-primary-600 border-primary-300 rounded accent-primary-600'
            }),
            'extraction_when': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all'
            }),
            'anesthesia_allergy': forms.CheckboxInput(attrs={
                'class': 'w-4 h-4 text-primary-600 border-primary-300 rounded accent-primary-600'
            }),
            'anesthesia_allergy_when': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all'
            }),
            'dental_appliance': forms.CheckboxInput(attrs={
                'class': 'w-4 h-4 text-primary-600 border-primary-300 rounded accent-primary-600'
            }),
            'appliance_type': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all',
                'placeholder': 'e.g., braces, retainer, dentures'
            }),
            'pain_discomfort': forms.CheckboxInput(attrs={
                'class': 'w-4 h-4 text-primary-600 border-primary-300 rounded accent-primary-600'
            }),
            'pain_location': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all',
                'rows': 3,
                'placeholder': 'Describe location and type of pain'
            }),
        }


class PediatricDentalHistoryForm(forms.ModelForm):
    """Form for pediatric dental history"""
    
    class Meta:
        model = PediatricDentalHistory
        fields = [
            'child_mouth_condition', 'normal_pregnancy_birth', 'bottle_at_bedtime',
            'last_dentist_visit', 'first_tooth_age_months',
            'thumb_sucking', 'tongue_thrusting', 'nail_biting',
            'mouth_breathing', 'teeth_grinding', 'other_habits'
        ]
        widgets = {
            'child_mouth_condition': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all',
                'rows': 3
            }),
            'normal_pregnancy_birth': forms.CheckboxInput(attrs={
                'class': 'w-4 h-4 text-primary-600 border-primary-300 rounded accent-primary-600'
            }),
            'bottle_at_bedtime': forms.CheckboxInput(attrs={
                'class': 'w-4 h-4 text-primary-600 border-primary-300 rounded accent-primary-600'
            }),
            'last_dentist_visit': forms.DateInput(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all',
                'type': 'date'
            }),
            'first_tooth_age_months': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all',
                'min': '0',
                'max': '36'
            }),
            'thumb_sucking': forms.CheckboxInput(attrs={
                'class': 'w-4 h-4 text-primary-600 border-primary-300 rounded accent-primary-600'
            }),
            'tongue_thrusting': forms.CheckboxInput(attrs={
                'class': 'w-4 h-4 text-primary-600 border-primary-300 rounded accent-primary-600'
            }),
            'nail_biting': forms.CheckboxInput(attrs={
                'class': 'w-4 h-4 text-primary-600 border-primary-300 rounded accent-primary-600'
            }),
            'mouth_breathing': forms.CheckboxInput(attrs={
                'class': 'w-4 h-4 text-primary-600 border-primary-300 rounded accent-primary-600'
            }),
            'teeth_grinding': forms.CheckboxInput(attrs={
                'class': 'w-4 h-4 text-primary-600 border-primary-300 rounded accent-primary-600'
            }),
            'other_habits': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all',
                'rows': 3
            }),
        }


class DentalChartForm(forms.ModelForm):
    """Form for individual tooth record"""
    
    class Meta:
        model = DentalChart
        fields = ['tooth_number', 'tooth_type', 'condition', 'notes']
        widgets = {
            'tooth_number': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all',
                'min': '1',
                'max': '85'
            }),
            'tooth_type': forms.Select(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all'
            }),
            'condition': forms.Select(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all',
                'rows': 3
            }),
        }


class ProgressNoteForm(forms.ModelForm):
    """Form for progress notes"""
    
    class Meta:
        model = ProgressNote
        fields = ['date', 'procedure_done', 'dentist', 'remarks']
        widgets = {
            'date': forms.DateInput(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all',
                'type': 'date'
            }),
            'procedure_done': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all',
                'rows': 3,
                'placeholder': 'Description of the procedure performed'
            }),
            'dentist': forms.Select(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all'
            }),
            'remarks': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all',
                'rows': 3,
                'placeholder': 'Additional remarks or notes'
            }),
        }
        labels = {
            'date': 'Date',
            'procedure_done': 'Procedure Done',
            'dentist': 'Dentist',
            'remarks': 'Remarks',
        }
