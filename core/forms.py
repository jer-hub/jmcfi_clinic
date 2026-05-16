import re

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from .models import (
    StudentProfile,
    StaffProfile,
    CollegeDepartment,
    CourseProgram,
    YearLevelOption,
)

User = get_user_model()
PH_STRICT_E164_RE = re.compile(r'^\+63\d{10}$')
OPTIONAL_COURSE_DEPARTMENTS = {
    'IBED - Primary',
    'IBED - Junior High School',
    'IBED - Junior Highschool',
}


# ---------------------------------------------------------------------------
# Shared phone-field widget attrs
# ---------------------------------------------------------------------------

PHONE_WIDGET_ATTRS = {
    'class': (
        'block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm '
        'placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-primary-500 '
        'focus:border-primary-500 sm:text-sm'
    ),
    'type': 'tel',
    'placeholder': '9XXXXXXXXX',
    'inputmode': 'numeric',
    'autocomplete': 'tel',
    'pattern': '^\+63\d{10}$',
    'title': 'Use format +63 followed by 10 digits (e.g., +639171234567).',
    'maxlength': '13',
    'minlength': '13',
}


def clean_strict_ph_number(value, required=False):
    value = (value or '').strip()
    if not value:
        if required:
            raise forms.ValidationError('This field is required.')
        return ''
    if not PH_STRICT_E164_RE.fullmatch(value):
        raise forms.ValidationError('Enter a valid Philippine number in +63XXXXXXXXXX format.')
    return value


class AdminLoginForm(forms.Form):
    """Password login form restricted to admin-role authentication flow."""

    email = forms.EmailField(
        widget=forms.EmailInput(
            attrs={
                'class': (
                    'block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm '
                    'placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-primary-500 '
                    'focus:border-primary-500 sm:text-sm'
                ),
                'placeholder': 'admin@jmcfi.edu.ph',
                'autocomplete': 'email',
                'required': True,
            }
        )
    )
    password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                'class': (
                    'block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm '
                    'placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-primary-500 '
                    'focus:border-primary-500 sm:text-sm'
                ),
                'placeholder': 'Enter password',
                'autocomplete': 'current-password',
                'required': True,
            }
        )
    )
    remember_me = forms.BooleanField(required=False)

    def clean_email(self):
        return (self.cleaned_data.get('email') or '').strip().lower()


class StudentProfileForm(forms.ModelForm):
    """Form for updating student profile including profile image"""
    
    # Override phone fields with enhanced widget (validation handled in clean methods)
    phone = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={**PHONE_WIDGET_ATTRS, 'required': True}),
    )
    
    emergency_phone = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={**PHONE_WIDGET_ATTRS, 'required': True}),
    )
    
    class Meta:
        model = StudentProfile
        fields = [
            'student_id', 'profile_image', 
            # Demographics
            'middle_name', 'gender', 'civil_status', 'date_of_birth', 'place_of_birth', 'age',
            # Contact Information
            'address', 'phone', 'telephone_number', 'emergency_contact', 'emergency_phone',
            # Institutional Information
            'course', 'year_level', 'department',
            # Medical Information
            'blood_type', 'allergies', 'medical_conditions'
        ]
        widgets = {
            'student_id': forms.TextInput(attrs={
                'class': 'block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 sm:text-sm font-mono',
                'placeholder': 'Enter your student ID',
                'required': True
            }),
            'profile_image': forms.FileInput(attrs={
                'class': 'hidden',
                'accept': 'image/*',
                'id': 'profile-image-input',
                'x-ref': 'profileImageInput',
                '@change': 'handleFileChange($event)',
            }),
            'middle_name': forms.TextInput(attrs={
                'class': 'block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 sm:text-sm',
                'placeholder': 'Middle Name',
                'required': True,
            }),
            'gender': forms.Select(attrs={
                'class': 'block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 sm:text-sm',
                'required': True
            }),
            'civil_status': forms.Select(attrs={
                'class': 'block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 sm:text-sm',
                'required': True
            }),
            'date_of_birth': forms.DateInput(attrs={
                'class': 'block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 sm:text-sm',
                'type': 'date',
                'required': True
            }),
            'place_of_birth': forms.TextInput(attrs={
                'class': 'block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 sm:text-sm',
                'placeholder': 'City/Province',
                'required': True
            }),
            'age': forms.NumberInput(attrs={
                'class': 'block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 sm:text-sm',
                'min': '0',
                'max': '150',
                'required': True
            }),
            'address': forms.Textarea(attrs={
                'class': 'block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 sm:text-sm resize-none',
                'rows': 3,
                'placeholder': 'Complete residential address',
                'required': True
            }),
            'telephone_number': forms.TextInput(attrs={
                **PHONE_WIDGET_ATTRS,
                'required': False,
            }),
            'emergency_contact': forms.TextInput(attrs={
                'class': 'block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 sm:text-sm',
                'placeholder': 'Emergency contact name',
                'required': True
            }),
            'course': forms.TextInput(attrs={
                'class': 'block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 sm:text-sm',
                'placeholder': 'e.g., BS Computer Science',
                'required': True
            }),
            'year_level': forms.TextInput(attrs={
                'class': 'block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 sm:text-sm',
                'placeholder': 'e.g., 1st Year, 2nd Year',
                'required': True
            }),
            'department': forms.TextInput(attrs={
                'class': 'block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 sm:text-sm',
                'placeholder': 'College/Department',
                'required': True
            }),
            'blood_type': forms.Select(attrs={
                'class': 'block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 sm:text-sm',
                'required': True
            }),
            'allergies': forms.Textarea(attrs={
                'class': 'block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 sm:text-sm resize-none',
                'rows': 4,
                'placeholder': 'List any allergies (food, medication, environmental, etc.) or write "None"'
            }),
            'medical_conditions': forms.Textarea(attrs={
                'class': 'block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 sm:text-sm resize-none',
                'rows': 4,
                'placeholder': 'List any existing medical conditions or chronic illnesses or write "None"'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add empty choice for select fields
        self.fields['blood_type'].empty_label = "Select your blood type"
        self.fields['gender'].empty_label = "Select gender"
        self.fields['civil_status'].empty_label = "Select civil status"
        
        # Set required fields
        required_fields = [
            'student_id', 'middle_name', 'gender', 'civil_status', 'date_of_birth', 'place_of_birth', 'age',
            'address', 'phone', 'emergency_contact', 'emergency_phone',
            'year_level', 'department', 'blood_type'
        ]
        for field_name in required_fields:
            if field_name in self.fields:
                self.fields[field_name].required = True

        # Required student contact fields prefill +63.
        for contact_field in ['phone', 'emergency_phone']:
            current_value = self.initial.get(contact_field)
            if not current_value and self.instance and self.instance.pk:
                current_value = getattr(self.instance, contact_field, '')
            if not current_value:
                self.initial[contact_field] = '+63'

    def clean_phone(self):
        return clean_strict_ph_number(self.cleaned_data.get('phone'), required=True)

    def clean(self):
        cleaned_data = super().clean()

        department = (cleaned_data.get('department') or '').strip()
        course = (cleaned_data.get('course') or '').strip()
        year_level = (cleaned_data.get('year_level') or '').strip()

        if not department:
            return cleaned_data

        if not CollegeDepartment.objects.filter(is_active=True, name=department).exists():
            self.add_error('department', 'Select a valid College/Department.')
            return cleaned_data

        course_is_optional = department in OPTIONAL_COURSE_DEPARTMENTS
        if not course and not course_is_optional:
            self.add_error('course', 'Course/Program is required for the selected College/Department.')

        if course and not CourseProgram.objects.filter(
            is_active=True,
            college_department__name=department,
            name=course,
        ).exists():
            self.add_error('course', 'Course/Program must match the selected College/Department.')

        if year_level and not YearLevelOption.objects.filter(
            is_active=True,
            college_department__name=department,
            name=year_level,
        ).exists():
            self.add_error('year_level', 'Year Level must match the selected College/Department.')

        return cleaned_data

    def clean_telephone_number(self):
        return clean_strict_ph_number(self.cleaned_data.get('telephone_number'), required=False)

    def clean_emergency_phone(self):
        return clean_strict_ph_number(self.cleaned_data.get('emergency_phone'), required=True)

    def clean_student_id(self):
        student_id = self.cleaned_data.get('student_id')
        if not student_id or student_id.startswith('TEMP_'):
            raise forms.ValidationError('Please provide a valid student ID.')
        return student_id


class StaffProfileForm(forms.ModelForm):
    """Form for updating staff profile including profile image"""
    
    # Override phone fields with enhanced widget (validation handled in clean methods)
    phone = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={**PHONE_WIDGET_ATTRS, 'required': True}),
    )
    
    emergency_phone = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs=PHONE_WIDGET_ATTRS),
    )
    
    class Meta:
        model = StaffProfile
        fields = [
            'staff_id', 'profile_image',
            # Demographics
            'middle_name', 'gender', 'civil_status', 'date_of_birth', 'place_of_birth', 'age',
            # Contact Information
            'address', 'phone', 'telephone_number', 'emergency_contact', 'emergency_phone',
            # Institutional Information
            'department', 'position', 'specialization', 'license_number',
            'ptr_no',
            # Medical Information
            'blood_type', 'allergies', 'medical_conditions'
        ]
        widgets = {
            'staff_id': forms.TextInput(attrs={
                'class': 'block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 sm:text-sm font-mono',
                'placeholder': 'Enter your staff ID',
                'required': True
            }),
            'profile_image': forms.FileInput(attrs={
                'class': 'hidden',
                'accept': 'image/*',
                'id': 'profile-image-input',
                'x-ref': 'profileImageInput',
                '@change': 'handleFileChange($event)',
            }),
            'middle_name': forms.TextInput(attrs={
                'class': 'block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 sm:text-sm',
                'placeholder': 'Middle Name'
            }),
            'gender': forms.Select(attrs={
                'class': 'block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 sm:text-sm',
                'required': True
            }),
            'civil_status': forms.Select(attrs={
                'class': 'block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 sm:text-sm',
                'required': True
            }),
            'date_of_birth': forms.DateInput(attrs={
                'class': 'block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 sm:text-sm',
                'type': 'date',
                'required': True
            }),
            'place_of_birth': forms.TextInput(attrs={
                'class': 'block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 sm:text-sm',
                'placeholder': 'City/Province',
                'required': True
            }),
            'age': forms.NumberInput(attrs={
                'class': 'block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 sm:text-sm',
                'min': '0',
                'max': '150',
                'required': True
            }),
            'address': forms.Textarea(attrs={
                'class': 'block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 sm:text-sm resize-none',
                'rows': 3,
                'placeholder': 'Complete residential address',
                'required': True
            }),
            'telephone_number': forms.TextInput(attrs={
                **PHONE_WIDGET_ATTRS,
            }),
            'emergency_contact': forms.TextInput(attrs={
                'class': 'block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 sm:text-sm',
                'placeholder': 'Emergency contact name',
                'required': True
            }),
            'blood_type': forms.Select(attrs={
                'class': 'block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 sm:text-sm'
            }),
            'allergies': forms.Textarea(attrs={
                'class': 'block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 sm:text-sm resize-none',
                'rows': 4,
                'placeholder': 'List any allergies (food, medication, environmental, etc.) or write "None"'
            }),
            'medical_conditions': forms.Textarea(attrs={
                'class': 'block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 sm:text-sm resize-none',
                'rows': 4,
                'placeholder': 'List any existing medical conditions or chronic illnesses or write "None"'
            }),
            'department': forms.TextInput(attrs={
                'class': 'block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 sm:text-sm',
                'placeholder': 'e.g., Cardiology, General Medicine',
                'required': True
            }),
            'position': forms.TextInput(attrs={
                'class': 'block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 sm:text-sm',
                'placeholder': 'Your position/title',
                'required': True
            }),
            'specialization': forms.TextInput(attrs={
                'class': 'block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 sm:text-sm',
                'placeholder': 'Your area of specialization'
            }),
            'license_number': forms.TextInput(attrs={
                'class': 'block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 sm:text-sm font-mono',
                'placeholder': 'Medical license number'
            }),
            'ptr_no': forms.TextInput(attrs={
                'class': 'block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 sm:text-sm font-mono',
                'placeholder': 'PTR No. / Professional Tax Receipt'
            }),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        role = None
        if self.user is not None:
            role = getattr(self.user, 'role', None)
        elif self.instance and self.instance.pk and getattr(self.instance, 'user', None):
            role = getattr(self.instance.user, 'role', None)

        # Add empty choice for select fields
        self.fields['blood_type'].empty_label = "Select your blood type (optional)"
        self.fields['gender'].empty_label = "Select gender"
        self.fields['civil_status'].empty_label = "Select civil status"
        
        # Set required fields
        required_fields = [
            'staff_id', 'gender', 'civil_status', 'date_of_birth', 'place_of_birth', 'age',
            'address', 'phone', 'emergency_contact', 
            'department', 'position'
        ]
        for field_name in required_fields:
            if field_name in self.fields:
                self.fields[field_name].required = True

        # Required staff contact field prefill +63.
        current_phone = self.initial.get('phone')
        if not current_phone and self.instance and self.instance.pk:
            current_phone = getattr(self.instance, 'phone', '')
        if not current_phone:
            self.initial['phone'] = '+63'

        # Doctor onboarding: force doctor-only credentials and hide unrelated health-self fields.
        if role == 'doctor':
            if 'license_number' in self.fields:
                self.fields['license_number'].required = True
            if 'ptr_no' in self.fields:
                self.fields['ptr_no'].required = True
            if 'position' in self.fields:
                self.fields['position'].required = True

            for hidden_field in ['blood_type', 'allergies', 'medical_conditions']:
                if hidden_field in self.fields:
                    self.fields.pop(hidden_field)
        else:
            if 'license_number' in self.fields:
                self.fields['license_number'].required = False
            if 'ptr_no' in self.fields:
                self.fields['ptr_no'].required = False

        if role == 'admin':
            # Admin profiles should not collect professional or medical-health details.
            for hidden_field in [
                'department',
                'position',
                'specialization',
                'license_number',
                'ptr_no',
                'blood_type',
                'allergies',
                'medical_conditions',
            ]:
                if hidden_field in self.fields:
                    self.fields.pop(hidden_field)

    def clean_phone(self):
        return clean_strict_ph_number(self.cleaned_data.get('phone'), required=True)

    def clean_telephone_number(self):
        return clean_strict_ph_number(self.cleaned_data.get('telephone_number'), required=False)

    def clean_emergency_phone(self):
        return clean_strict_ph_number(self.cleaned_data.get('emergency_phone'), required=False)

    def clean_staff_id(self):
        staff_id = self.cleaned_data.get('staff_id')
        if not staff_id or staff_id.startswith('TEMP_'):
            raise forms.ValidationError('Please provide a valid staff ID.')
        return staff_id

    def clean_department(self):
        department = self.cleaned_data.get('department')
        if not department or not department.strip():
            raise forms.ValidationError('Department is required.')
        return department.strip()


class UserCreationForm(forms.ModelForm):
    """Form for creating new users (students or staff)"""

    activate_now = forms.BooleanField(
        required=False,
        initial=False,
        label='Activate account now',
        widget=forms.CheckboxInput(attrs={
            'class': 'h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded'
        })
    )
    
    password1 = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={
            'class': 'block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500',
            'placeholder': 'Enter password'
        })
    )
    password2 = forms.CharField(
        label='Confirm Password',
        widget=forms.PasswordInput(attrs={
            'class': 'block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500',
            'placeholder': 'Confirm password'
        })
    )
    
    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'role']
        widgets = {
            'username': forms.TextInput(attrs={
                'class': 'block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500',
                'placeholder': 'Enter username'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500',
                'placeholder': 'Enter email address'
            }),
            'first_name': forms.TextInput(attrs={
                'class': 'block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500',
                'placeholder': 'Enter first name'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500',
                'placeholder': 'Enter last name'
            }),
            'role': forms.Select(attrs={
                'class': 'block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500'
            })
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Limit role choices to student, staff, and doctor only
        self.fields['role'].choices = [
            ('admin', 'Admin'),
            ('student', 'Student'),
            ('staff', 'Staff'),
            ('doctor', 'Doctor'),
        ]
        # Make required fields (username is optional)
        for field_name in ['email', 'first_name', 'last_name', 'role']:
            self.fields[field_name].required = True
        self.fields['username'].required = False
    
    def clean_password2(self):
        password1 = self.cleaned_data.get('password1')
        password2 = self.cleaned_data.get('password2')
        
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("Passwords don't match")

        if password1:
            user_for_validation = User(
                email=(self.cleaned_data.get('email') or '').strip().lower(),
                username=self.cleaned_data.get('username') or None,
                first_name=(self.cleaned_data.get('first_name') or '').strip(),
                last_name=(self.cleaned_data.get('last_name') or '').strip(),
                role=self.cleaned_data.get('role') or User.ROLE.STUDENT,
            )
            try:
                validate_password(password1, user=user_for_validation)
            except DjangoValidationError as exc:
                raise forms.ValidationError(exc.messages)
        
        return password2
    
    def clean_email(self):
        email = (self.cleaned_data.get('email') or '').strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("A user with this email already exists")
        return email

    def clean_username(self):
        username = (self.cleaned_data.get('username') or '').strip()
        if not username:
            return None

        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("A user with this username already exists")
        return username
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password1'])
        if self.cleaned_data.get('activate_now'):
            user.is_active = True
            user.onboarding_status = User.ONBOARDING_STATUS.ACTIVE
        else:
            user.is_active = False
            user.onboarding_status = User.ONBOARDING_STATUS.PENDING_ACTIVATION
        
        if commit:
            user.save()
            # Create profile based on role
            if user.role == 'student':
                StudentProfile.objects.get_or_create(
                    user=user,
                    defaults={
                        'student_id': f'TEMP_{user.id}',
                        'phone': '',
                        'emergency_contact': '',
                        'emergency_phone': '',
                        'date_of_birth': '2000-01-01',
                    }
                )
            elif user.role in ['staff', 'doctor', 'admin']:
                StaffProfile.objects.get_or_create(
                    user=user,
                    defaults={
                        'staff_id': f'TEMP_{user.id}',
                        'phone': '',
                        'department': 'Pending',
                    }
                )
        
        return user


class UserEditForm(forms.ModelForm):
    """Form for editing existing users"""
    
    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'role', 'is_active']
        widgets = {
            'username': forms.TextInput(attrs={
                'class': 'block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500',
                'placeholder': 'Enter username'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500',
                'placeholder': 'Enter email address'
            }),
            'first_name': forms.TextInput(attrs={
                'class': 'block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500',
                'placeholder': 'Enter first name'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500',
                'placeholder': 'Enter last name'
            }),
            'role': forms.Select(attrs={
                'class': 'block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded'
            })
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['role'].choices = [
            ('admin', 'Admin'),
            ('student', 'Student'),
            ('staff', 'Staff'),
            ('doctor', 'Doctor'),
        ]
        for field_name in ['email', 'first_name', 'last_name', 'role']:
            self.fields[field_name].required = True
        self.fields['username'].required = False
    
    def clean_email(self):
        email = (self.cleaned_data.get('email') or '').strip().lower()
        # Check if email exists for other users
        if User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("A user with this email already exists")
        return email

    def clean_username(self):
        username = (self.cleaned_data.get('username') or '').strip()
        if not username:
            return None

        if User.objects.filter(username__iexact=username).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("A user with this username already exists")
        return username


class PasswordResetForm(forms.Form):
    """Form for resetting user password by admin"""

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
    
    new_password1 = forms.CharField(
        label='New Password',
        widget=forms.PasswordInput(attrs={
            'class': 'block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500',
            'placeholder': 'Enter new password'
        })
    )
    new_password2 = forms.CharField(
        label='Confirm New Password',
        widget=forms.PasswordInput(attrs={
            'class': 'block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500',
            'placeholder': 'Confirm new password'
        })
    )
    
    def clean_new_password2(self):
        password1 = self.cleaned_data.get('new_password1')
        password2 = self.cleaned_data.get('new_password2')
        
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("Passwords don't match")

        if password1:
            try:
                validate_password(password1, user=self.user)
            except DjangoValidationError as exc:
                raise forms.ValidationError(exc.messages)
        
        return password2


class BulkUserActionForm(forms.Form):
    """Form for bulk operations on users (activate, deactivate, delete)."""

    ACTION_CHOICES = [
        ('activate', 'Activate Accounts'),
        ('deactivate', 'Deactivate Accounts'),
        ('delete', 'Soft Delete Accounts'),
    ]

    action = forms.ChoiceField(
        choices=ACTION_CHOICES,
        widget=forms.Select(attrs={
            'class': 'block w-full px-3 py-3 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 text-sm',
        })
    )
    user_ids = forms.CharField(
        widget=forms.HiddenInput(attrs={
            'id': 'bulk-user-ids',
        })
    )
    confirmation = forms.BooleanField(
        required=True,
        initial=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded',
        })
    )

    def clean_user_ids(self):
        raw = self.cleaned_data.get('user_ids', '')
        try:
            ids = [int(x.strip()) for x in raw.split(',') if x.strip()]
            if not ids:
                raise forms.ValidationError('No user IDs provided.')
            return ids
        except (ValueError, TypeError):
            raise forms.ValidationError('Invalid user IDs format.')

    def clean_action(self):
        action = self.cleaned_data.get('action', '')
        if action not in dict(self.ACTION_CHOICES):
            raise forms.ValidationError('Invalid action selected.')
        return action


class UserExportForm(forms.Form):
    """Form for filtering users to export."""

    role = forms.ChoiceField(
        required=False,
        choices=[('', 'All Roles'), ('student', 'Student'), ('staff', 'Staff'), ('doctor', 'Doctor'), ('admin', 'Admin')],
        widget=forms.Select(attrs={
            'class': 'block w-full px-3 py-3 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 text-sm',
        })
    )
    status = forms.ChoiceField(
        required=False,
        choices=[('', 'All Status'), ('active', 'Active'), ('pending', 'Pending Activation'), ('suspended', 'Suspended')],
        widget=forms.Select(attrs={
            'class': 'block w-full px-3 py-3 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 text-sm',
        })
    )
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'block w-full px-3 py-3 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 text-sm',
            'type': 'date',
        })
    )
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'block w-full px-3 py-3 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 text-sm',
            'type': 'date',
        })
    )
