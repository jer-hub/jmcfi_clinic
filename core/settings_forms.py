"""Forms for clinic-wide and per-role system settings."""

from django import forms

from .models import ClinicSettings, RoleSettings, User, UserPreferences

INPUT_CLASS = (
    'block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm '
    'placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-primary-500 '
    'focus:border-primary-500 sm:text-sm'
)
TEXTAREA_CLASS = INPUT_CLASS + ' min-h-[88px]'
CHECKBOX_CLASS = 'h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500'


class ClinicSettingsForm(forms.ModelForm):
    class Meta:
        model = ClinicSettings
        fields = [
            'clinic_name',
            'logo',
            'support_email',
            'support_phone',
            'timezone',
            'date_format',
            'google_allowed_domains',
            'allow_patient_self_signup',
            'default_session_hours',
            'appointment_interval_minutes',
            'max_advance_booking_days',
            'cancellation_cutoff_hours',
            'enable_email_notifications',
            'digest_hour',
            'maintenance_mode',
            'maintenance_message',
        ]
        widgets = {
            'clinic_name': forms.TextInput(attrs={'class': INPUT_CLASS}),
            'logo': forms.ClearableFileInput(attrs={'class': INPUT_CLASS}),
            'support_email': forms.EmailInput(attrs={'class': INPUT_CLASS}),
            'support_phone': forms.TextInput(attrs={'class': INPUT_CLASS}),
            'timezone': forms.TextInput(attrs={'class': INPUT_CLASS}),
            'date_format': forms.TextInput(attrs={'class': INPUT_CLASS}),
            'google_allowed_domains': forms.Textarea(
                attrs={'class': TEXTAREA_CLASS, 'rows': 2, 'placeholder': 'jmc.edu.ph, jmcfi.edu.ph'},
            ),
            'allow_patient_self_signup': forms.CheckboxInput(attrs={'class': CHECKBOX_CLASS}),
            'default_session_hours': forms.NumberInput(attrs={'class': INPUT_CLASS, 'min': 1, 'max': 168}),
            'appointment_interval_minutes': forms.NumberInput(attrs={'class': INPUT_CLASS, 'min': 15, 'max': 120}),
            'max_advance_booking_days': forms.NumberInput(attrs={'class': INPUT_CLASS, 'min': 1, 'max': 365}),
            'cancellation_cutoff_hours': forms.NumberInput(attrs={'class': INPUT_CLASS, 'min': 0, 'max': 168}),
            'enable_email_notifications': forms.CheckboxInput(attrs={'class': CHECKBOX_CLASS}),
            'digest_hour': forms.NumberInput(attrs={'class': INPUT_CLASS, 'min': 0, 'max': 23}),
            'maintenance_mode': forms.CheckboxInput(attrs={'class': CHECKBOX_CLASS}),
            'maintenance_message': forms.Textarea(attrs={'class': TEXTAREA_CLASS, 'rows': 3}),
        }

    def clean_appointment_interval_minutes(self):
        value = self.cleaned_data['appointment_interval_minutes']
        if value < 15 or value > 120:
            raise forms.ValidationError('Must be between 15 and 120 minutes.')
        return value

    def clean_digest_hour(self):
        value = self.cleaned_data['digest_hour']
        if value < 0 or value > 23:
            raise forms.ValidationError('Must be between 0 and 23.')
        return value

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('maintenance_mode') and not (cleaned.get('maintenance_message') or '').strip():
            self.add_error(
                'maintenance_message',
                'Provide a message when maintenance mode is enabled.',
            )
        return cleaned


class RoleSettingsForm(forms.ModelForm):
    session_timeout_hours = forms.IntegerField(
        min_value=1,
        max_value=168,
        help_text='How long users stay signed in before the session expires.',
        widget=forms.NumberInput(attrs={'class': INPUT_CLASS, 'min': 1, 'max': 168}),
    )
    profile_required_fields_text = forms.CharField(
        required=False,
        help_text='One field name per line (or comma-separated). Used for profile completion checks.',
        widget=forms.Textarea(attrs={'class': TEXTAREA_CLASS, 'rows': 8}),
    )

    class Meta:
        model = RoleSettings
        fields = [
            'can_access_analytics',
            'can_submit_feedback',
            'can_use_messaging',
            'can_book_appointments',
            'block_clinical_namespaces',
            'show_health_tips_nav',
        ]
        widgets = {
            'can_access_analytics': forms.CheckboxInput(attrs={'class': CHECKBOX_CLASS}),
            'can_submit_feedback': forms.CheckboxInput(attrs={'class': CHECKBOX_CLASS}),
            'can_use_messaging': forms.CheckboxInput(attrs={'class': CHECKBOX_CLASS}),
            'can_book_appointments': forms.CheckboxInput(attrs={'class': CHECKBOX_CLASS}),
            'block_clinical_namespaces': forms.CheckboxInput(attrs={'class': CHECKBOX_CLASS}),
            'show_health_tips_nav': forms.CheckboxInput(attrs={'class': CHECKBOX_CLASS}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            hours = max(1, self.instance.session_timeout_seconds // 3600)
            self.fields['session_timeout_hours'].initial = hours
            fields = self.instance.profile_required_fields or []
            self.fields['profile_required_fields_text'].initial = '\n'.join(fields)

    def clean_profile_required_fields_text(self):
        raw = (self.cleaned_data.get('profile_required_fields_text') or '').strip()
        if not raw:
            return []
        parts = []
        for line in raw.replace(',', '\n').split('\n'):
            name = line.strip()
            if name and name not in parts:
                parts.append(name)
        return parts

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.session_timeout_seconds = self.cleaned_data['session_timeout_hours'] * 3600
        instance.profile_required_fields = self.cleaned_data['profile_required_fields_text']
        if commit:
            instance.save()
        return instance


class UserPreferencesForm(forms.ModelForm):
    class Meta:
        model = UserPreferences
        fields = [
            'email_notifications',
            'in_app_notifications',
            'compact_nav',
        ]
        widgets = {
            'email_notifications': forms.CheckboxInput(attrs={'class': CHECKBOX_CLASS}),
            'in_app_notifications': forms.CheckboxInput(attrs={'class': CHECKBOX_CLASS}),
            'compact_nav': forms.CheckboxInput(attrs={'class': CHECKBOX_CLASS}),
        }


def is_valid_settings_role(role: str) -> bool:
    return role in {choice[0] for choice in User.ROLE.choices}
