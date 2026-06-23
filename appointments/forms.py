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
        help_text='Select doctors available for this appointment type. Select all for open booking, a subset to restrict, or none to block booking.',
    )

    class Meta:
        model = AppointmentTypeDefault
        fields = ['appointment_type', 'assigned_doctors']  # Removed is_active - handled separately by toggle
        widgets = {
            'appointment_type': forms.Select(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary-500 focus:ring-primary-500 sm:text-sm'
            }),
        }
        labels = {
            'appointment_type': 'Appointment Type',
        }
        help_texts = {
            'appointment_type': 'Select the type of appointment',
        }

    def __init__(self, *args, doctors_qs=None, **kwargs):
        super().__init__(*args, **kwargs)
        if doctors_qs is None:
            doctors_qs = User.objects.filter(
                role__in=['doctor', 'staff'],
                is_active=True,
            ).select_related('staff_profile').order_by('first_name', 'last_name')

        self.fields['assigned_doctors'].queryset = doctors_qs

        def doctor_label(obj):
            dept = obj.staff_profile.department if hasattr(obj, 'staff_profile') and obj.staff_profile else 'N/A'
            prefix = 'Dr. ' if obj.role == 'doctor' else ''
            return f"{prefix}{obj.get_full_name()} - {dept}"

        self.fields['assigned_doctors'].label_from_instance = doctor_label

        if self.instance and self.instance.pk:
            self.fields['appointment_type'].widget.attrs['disabled'] = 'disabled'
            self.fields['appointment_type'].required = False

    def clean_appointment_type(self):
        # Ensure appointment_type doesn't change on edit
        if self.instance and self.instance.pk:
            return self.instance.appointment_type
        return self.cleaned_data.get('appointment_type')
