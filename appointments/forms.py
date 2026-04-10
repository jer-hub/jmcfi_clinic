from django import forms
from django.contrib.auth import get_user_model
from .models import Appointment, AppointmentTypeDefault

User = get_user_model()


class AppointmentTypeDefaultForm(forms.ModelForm):
    """Form for admin users to assign doctors to each appointment type"""

    assigned_doctors = forms.ModelMultipleChoiceField(
        queryset=User.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded'
        }),
        label='Assigned Doctors',
        help_text='Select one or more doctors available for this appointment type. If none are selected, all active doctors will be available.',
    )

    class Meta:
        model = AppointmentTypeDefault
        fields = ['appointment_type', 'assigned_doctors', 'is_active']
        widgets = {
            'appointment_type': forms.Select(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded'
            }),
        }
        labels = {
            'appointment_type': 'Appointment Type',
            'is_active': 'Active',
        }
        help_texts = {
            'appointment_type': 'Select the type of appointment',
            'is_active': 'Check if this setting should be active',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        doctors_qs = User.objects.filter(
            role='doctor',
            is_active=True
        ).order_by('first_name', 'last_name')

        self.fields['assigned_doctors'].queryset = doctors_qs

        def doctor_label(obj):
            dept = obj.staff_profile.department if hasattr(obj, 'staff_profile') and obj.staff_profile else 'N/A'
            return f"Dr. {obj.get_full_name()} - {dept}"

        self.fields['assigned_doctors'].label_from_instance = doctor_label

        # Make appointment_type readonly when editing (can't change type once created)
        if self.instance and self.instance.pk:
            self.fields['appointment_type'].widget.attrs['disabled'] = 'disabled'
            self.fields['appointment_type'].required = False

    def clean_appointment_type(self):
        # Ensure appointment_type doesn't change on edit
        if self.instance and self.instance.pk:
            return self.instance.appointment_type
        return self.cleaned_data.get('appointment_type')
