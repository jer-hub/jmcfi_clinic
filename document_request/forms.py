from django import forms
from .models import DocumentRequest


class DocumentRequestForm(forms.ModelForm):
    """Form for creating document/certificate requests."""
    
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
