from django import forms
from django.core.validators import RegexValidator
from .models import StudentProfile, StaffProfile

class StudentProfileForm(forms.ModelForm):
    """Form for updating student profile including profile image"""
    
    # Philippines phone number validator - strict for mobile numbers only
    phone_validator = RegexValidator(
        regex=r'^(\+63|63|0)?(9[0-9]{9})$',
        message='Enter a valid Philippine mobile number (e.g., +639171234567, 09171234567)'
    )
    
    # Override phone fields with validation
    phone = forms.CharField(
        max_length=20,
        validators=[phone_validator],
        widget=forms.TextInput(attrs={
            'class': 'block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 sm:text-sm',
            'placeholder': '+639171234567 or 09171234567',
            'required': True,
            'data-phone-input': 'true'
        })
    )
    
    emergency_phone = forms.CharField(
        max_length=20,
        validators=[phone_validator],
        widget=forms.TextInput(attrs={
            'class': 'block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 sm:text-sm',
            'placeholder': '+639171234567 or 09171234567',
            'required': True,
            'data-phone-input': 'true'
        })
    )
    
    class Meta:
        model = StudentProfile
        fields = ['student_id', 'profile_image', 'date_of_birth', 'phone', 'emergency_contact', 
                 'emergency_phone', 'blood_type', 'allergies', 'medical_conditions']
        widgets = {
            'student_id': forms.TextInput(attrs={
                'class': 'block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 sm:text-sm font-mono',
                'placeholder': 'Enter your student ID',
                'required': True
            }),
            'profile_image': forms.FileInput(attrs={
                'class': 'hidden',
                'accept': 'image/*',
                'id': 'profile-image-input'
            }),
            'date_of_birth': forms.DateInput(attrs={
                'class': 'block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 sm:text-sm',
                'type': 'date',
                'required': True
            }),
            'emergency_contact': forms.TextInput(attrs={
                'class': 'block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 sm:text-sm',
                'placeholder': 'Emergency contact name',
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
        # Add empty choice for blood type to make selection required
        self.fields['blood_type'].empty_label = "Select your blood type"
        # Set required fields
        required_fields = ['student_id', 'date_of_birth', 'phone', 'emergency_contact', 'emergency_phone', 'blood_type']
        for field_name in required_fields:
            if field_name in self.fields:
                self.fields[field_name].required = True

    def clean_phone(self):
        phone = self.cleaned_data.get('phone')
        if phone:
            # Remove all non-digit characters for processing
            cleaned = ''.join(filter(str.isdigit, phone))
            
            # Validate Philippine mobile number format (strict)
            if cleaned.startswith('63'):
                # +63 format - must be 12 digits and 3rd digit must be 9
                if len(cleaned) == 12 and cleaned[2] == '9':
                    return f"+{cleaned}"
                elif len(cleaned) == 13 and cleaned.startswith('630') and cleaned[3] == '9':
                    # Remove leading 0 after country code
                    return f"+63{cleaned[3:]}"
            elif cleaned.startswith('0'):
                # 0 prefix format (e.g., 09171234567) - must be 11 digits and 2nd digit must be 9
                if len(cleaned) == 11 and cleaned[1] == '9':
                    return f"+63{cleaned[1:]}"
            elif len(cleaned) == 10 and cleaned[0] == '9':
                # Without country code or 0 prefix (e.g., 9171234567) - must start with 9
                return f"+63{cleaned}"
            
            # If none of the valid patterns match, raise validation error
            raise forms.ValidationError('Please enter a valid Philippine mobile number starting with 9.')
        return phone

    def clean_emergency_phone(self):
        phone = self.cleaned_data.get('emergency_phone')
        if phone:
            # Remove all non-digit characters for processing
            cleaned = ''.join(filter(str.isdigit, phone))
            
            # Validate Philippine mobile number format (strict)
            if cleaned.startswith('63'):
                # +63 format - must be 12 digits and 3rd digit must be 9
                if len(cleaned) == 12 and cleaned[2] == '9':
                    return f"+{cleaned}"
                elif len(cleaned) == 13 and cleaned.startswith('630') and cleaned[3] == '9':
                    # Remove leading 0 after country code
                    return f"+63{cleaned[3:]}"
            elif cleaned.startswith('0'):
                # 0 prefix format (e.g., 09171234567) - must be 11 digits and 2nd digit must be 9
                if len(cleaned) == 11 and cleaned[1] == '9':
                    return f"+63{cleaned[1:]}"
            elif len(cleaned) == 10 and cleaned[0] == '9':
                # Without country code or 0 prefix (e.g., 9171234567) - must start with 9
                return f"+63{cleaned}"
            
            # If none of the valid patterns match, raise validation error
            raise forms.ValidationError('Please enter a valid Philippine mobile number starting with 9.')
        return phone

    def clean_student_id(self):
        student_id = self.cleaned_data.get('student_id')
        if not student_id or student_id.startswith('TEMP_'):
            raise forms.ValidationError('Please provide a valid student ID.')
        return student_id

class StaffProfileForm(forms.ModelForm):
    """Form for updating staff profile including profile image"""
    
    # Philippines phone number validator - strict for mobile numbers only
    phone_validator = RegexValidator(
        regex=r'^(\+63|63|0)?(9[0-9]{9})$',
        message='Enter a valid Philippine mobile number (e.g., +639171234567, 09171234567)'
    )
    
    # Override phone fields with validation
    phone = forms.CharField(
        max_length=20,
        validators=[phone_validator],
        widget=forms.TextInput(attrs={
            'class': 'block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 sm:text-sm',
            'placeholder': '+639171234567 or 09171234567',
            'required': True,
            'data-phone-input': 'true'
        })
    )
    
    emergency_phone = forms.CharField(
        max_length=20,
        validators=[phone_validator],
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 sm:text-sm',
            'placeholder': '+639171234567 or 09171234567',
            'data-phone-input': 'true'
        })
    )
    
    class Meta:
        model = StaffProfile
        fields = ['staff_id', 'profile_image', 'date_of_birth', 'phone', 'emergency_contact', 
                 'emergency_phone', 'blood_type', 'allergies', 'medical_conditions', 
                 'department', 'specialization', 'license_number']
        widgets = {
            'staff_id': forms.TextInput(attrs={
                'class': 'block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 sm:text-sm font-mono',
                'placeholder': 'Enter your staff ID',
                'required': True
            }),
            'profile_image': forms.FileInput(attrs={
                'class': 'hidden',
                'accept': 'image/*',
                'id': 'profile-image-input'
            }),
            'date_of_birth': forms.DateInput(attrs={
                'class': 'block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 sm:text-sm',
                'type': 'date'
            }),
            'emergency_contact': forms.TextInput(attrs={
                'class': 'block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 sm:text-sm',
                'placeholder': 'Emergency contact name'
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
            'specialization': forms.TextInput(attrs={
                'class': 'block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 sm:text-sm',
                'placeholder': 'Your area of specialization'
            }),
            'license_number': forms.TextInput(attrs={
                'class': 'block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 sm:text-sm font-mono',
                'placeholder': 'Medical license number'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add empty choice for blood type
        self.fields['blood_type'].empty_label = "Select your blood type (optional)"
        # Set required fields
        required_fields = ['staff_id', 'department', 'phone']
        for field_name in required_fields:
            if field_name in self.fields:
                self.fields[field_name].required = True

    def clean_phone(self):
        phone = self.cleaned_data.get('phone')
        if phone:
            # Remove all non-digit characters for processing
            cleaned = ''.join(filter(str.isdigit, phone))
            
            # Validate Philippine mobile number format (strict)
            if cleaned.startswith('63'):
                # +63 format - must be 12 digits and 3rd digit must be 9
                if len(cleaned) == 12 and cleaned[2] == '9':
                    return f"+{cleaned}"
                elif len(cleaned) == 13 and cleaned.startswith('630') and cleaned[3] == '9':
                    # Remove leading 0 after country code
                    return f"+63{cleaned[3:]}"
            elif cleaned.startswith('0'):
                # 0 prefix format (e.g., 09171234567) - must be 11 digits and 2nd digit must be 9
                if len(cleaned) == 11 and cleaned[1] == '9':
                    return f"+63{cleaned[1:]}"
            elif len(cleaned) == 10 and cleaned[0] == '9':
                # Without country code or 0 prefix (e.g., 9171234567) - must start with 9
                return f"+63{cleaned}"
            
            # If none of the valid patterns match, raise validation error
            raise forms.ValidationError('Please enter a valid Philippine mobile number starting with 9.')
        return phone

    def clean_emergency_phone(self):
        phone = self.cleaned_data.get('emergency_phone')
        if phone:
            # Remove all non-digit characters for processing
            cleaned = ''.join(filter(str.isdigit, phone))
            
            # Validate Philippine mobile number format (strict)
            if cleaned.startswith('63'):
                # +63 format - must be 12 digits and 3rd digit must be 9
                if len(cleaned) == 12 and cleaned[2] == '9':
                    return f"+{cleaned}"
                elif len(cleaned) == 13 and cleaned.startswith('630') and cleaned[3] == '9':
                    # Remove leading 0 after country code
                    return f"+63{cleaned[3:]}"
            elif cleaned.startswith('0'):
                # 0 prefix format (e.g., 09171234567) - must be 11 digits and 2nd digit must be 9
                if len(cleaned) == 11 and cleaned[1] == '9':
                    return f"+63{cleaned[1:]}"
            elif len(cleaned) == 10 and cleaned[0] == '9':
                # Without country code or 0 prefix (e.g., 9171234567) - must start with 9
                return f"+63{cleaned}"
            
            # If none of the valid patterns match, raise validation error
            raise forms.ValidationError('Please enter a valid Philippine mobile number starting with 9.')
        return phone

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
