from django import forms
from .models import DocumentRequest, MedicalCertificate, DoctorSignature


class DocumentRequestForm(forms.ModelForm):
    """Form for creating document/certificate requests."""

    ALLOWED_DOCUMENT_TYPES = [('medical_certificate', 'Medical Certificate')]
    
    class Meta:
        model = DocumentRequest
        fields = ['document_type', 'purpose', 'additional_info']
        widgets = {
            'document_type': forms.Select(attrs={
                'class': 'block w-full px-4 py-3 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 text-sm transition-all duration-200 bg-white hover:border-primary-400',
                'required': True,
            }),
            'purpose': forms.TextInput(attrs={
                'class': 'block w-full px-4 py-3 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 text-sm transition-all duration-200 hover:border-primary-400',
                'placeholder': 'e.g., Job application, Sports participation, Travel',
                'required': True,
            }),
            'additional_info': forms.Textarea(attrs={
                'class': 'block w-full px-4 py-3 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 text-sm transition-all duration-200 hover:border-primary-400 resize-y',
                'rows': 4,
                'placeholder': 'Any additional details or special requirements...',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['document_type'].choices = self.ALLOWED_DOCUMENT_TYPES


class ProcessDocumentForm(forms.Form):
    """Form for processing document requests (approve/reject)."""
    
    ACTION_CHOICES = [
        ('approve', 'Approve'),
        ('reject', 'Reject'),
        ('ready', 'Mark as Ready'),
    ]
    
    action = forms.ChoiceField(choices=ACTION_CHOICES, widget=forms.HiddenInput())
    rejection_reason = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-red-500 focus:border-red-500',
            'rows': 4,
            'placeholder': 'Please provide a detailed reason for rejection...',
        })
    )
    
    def clean(self):
        cleaned_data = super().clean()
        action = cleaned_data.get('action')
        rejection_reason = cleaned_data.get('rejection_reason')
        
        if action == 'reject' and not rejection_reason:
            raise forms.ValidationError('Please provide a reason for rejection.')
        
        return cleaned_data


class MedicalCertificateForm(forms.ModelForm):
    """Form for creating/editing medical certificates."""

    class Meta:
        model = MedicalCertificate
        fields = [
            'certificate_date', 'patient_name', 'age', 'gender', 'address',
            'consultation_date', 'diagnosis', 'remarks_recommendations',
            'physician_name', 'license_no', 'ptr_no',
        ]
        widgets = {
            'certificate_date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'patient_name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Complete Name'}),
            'age': forms.NumberInput(attrs={'class': 'form-input'}),
            'gender': forms.Select(attrs={'class': 'form-select'}),
            'address': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 2}),
            'consultation_date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'diagnosis': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 5, 'placeholder': 'Enter diagnosis...'}),
            'remarks_recommendations': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 5, 'placeholder': 'Enter remarks and recommendations...'}),
            'physician_name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Signature over Printed Name'}),
            'license_no': forms.TextInput(attrs={'class': 'form-input'}),
            'ptr_no': forms.TextInput(attrs={'class': 'form-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['patient_name'].required = True


class DoctorSignatureForm(forms.ModelForm):
    """Doctor self-service form for uploading and managing signature."""

    class Meta:
        model = DoctorSignature
        fields = ['signature_image', 'is_active']
        widgets = {
            'signature_image': forms.ClearableFileInput(attrs={
                'class': 'form-input',
                'accept': 'image/png,image/jpeg,image/jpg,image/webp',
            }),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance or not self.instance.pk or not self.instance.signature_image:
            self.fields['signature_image'].required = True

    def clean_signature_image(self):
        signature_image = self.cleaned_data.get('signature_image')
        if signature_image is None and self.instance and self.instance.pk and self.instance.signature_image:
            return self.instance.signature_image
        return signature_image
