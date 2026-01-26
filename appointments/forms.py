from django import forms
from django.contrib.auth import get_user_model
from .models import Appointment, AppointmentTypeDefault

User = get_user_model()


class AppointmentTypeDefaultForm(forms.ModelForm):
    """Form for admin users to set default in-charge doctor for each appointment type"""
    
    class Meta:
        model = AppointmentTypeDefault
        fields = ['appointment_type', 'default_doctor', 'is_active']
        widgets = {
            'appointment_type': forms.Select(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm'
            }),
            'default_doctor': forms.Select(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded'
            }),
        }
        labels = {
            'appointment_type': 'Appointment Type',
            'default_doctor': 'Default In-Charge Doctor',
            'is_active': 'Active',
        }
        help_texts = {
            'appointment_type': 'Select the type of appointment',
            'default_doctor': 'Select the default doctor who will be assigned to this appointment type',
            'is_active': 'Check if this default setting should be active',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only show staff members (doctors) in the dropdown
        self.fields['default_doctor'].queryset = User.objects.filter(
            role__in=['staff', 'doctor'],
            is_active=True
        ).order_by('first_name', 'last_name')
        
        # Customize the display format for doctors
        self.fields['default_doctor'].label_from_instance = lambda obj: f"Dr. {obj.get_full_name()} - {obj.staff_profile.department if hasattr(obj, 'staff_profile') else 'N/A'}"
        
        # Make appointment_type readonly when editing (can't change type once created)
        if self.instance and self.instance.pk:
            self.fields['appointment_type'].widget.attrs['disabled'] = 'disabled'
            self.fields['appointment_type'].required = False

    def clean_appointment_type(self):
        # Ensure appointment_type doesn't change on edit
        if self.instance and self.instance.pk:
            return self.instance.appointment_type
        return self.cleaned_data.get('appointment_type')
