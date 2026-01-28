from django import forms
from django.core.validators import RegexValidator
from django.contrib.auth import get_user_model
from .models import StudentProfile, StaffProfile

User = get_user_model()


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
                'id': 'profile-image-input'
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
                'class': 'block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 sm:text-sm',
                'placeholder': 'Landline (optional)'
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
            'student_id', 'gender', 'civil_status', 'date_of_birth', 'place_of_birth', 'age',
            'address', 'phone', 'emergency_contact', 'emergency_phone',
            'course', 'year_level', 'department', 'blood_type'
        ]
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
        fields = [
            'staff_id', 'profile_image',
            # Demographics
            'middle_name', 'gender', 'civil_status', 'date_of_birth', 'place_of_birth', 'age',
            # Contact Information
            'address', 'phone', 'telephone_number', 'emergency_contact', 'emergency_phone',
            # Institutional Information
            'department', 'position', 'specialization', 'license_number',
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
                'id': 'profile-image-input'
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
                'class': 'block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 sm:text-sm',
                'placeholder': 'Landline (optional)'
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
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
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


class UserCreationForm(forms.ModelForm):
    """Form for creating new users (students or staff)"""
    
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
        
        if password1 and len(password1) < 8:
            raise forms.ValidationError("Password must be at least 8 characters long")
        
        return password2
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("A user with this email already exists")
        return email
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password1'])
        
        if commit:
            user.save()
            # Create profile based on role
            if user.role == 'student':
                StudentProfile.objects.create(
                    user=user,
                    student_id=f'TEMP_{user.id}',
                    phone='',
                    emergency_contact='',
                    emergency_phone='',
                    date_of_birth='2000-01-01'
                )
            elif user.role in ['staff', 'doctor']:
                StaffProfile.objects.create(
                    user=user,
                    staff_id=f'TEMP_{user.id}',
                    phone='',
                    department='Pending'
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
        # Limit role choices to student, staff, and doctor only
        self.fields['role'].choices = [
            ('student', 'Student'),
            ('staff', 'Staff'),
            ('doctor', 'Doctor'),
        ]
        # Make fields required (username is optional)
        for field_name in ['email', 'first_name', 'last_name', 'role']:
            self.fields[field_name].required = True
        self.fields['username'].required = False
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        # Check if email exists for other users
        if User.objects.filter(email=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("A user with this email already exists")
        return email


class PasswordResetForm(forms.Form):
    """Form for resetting user password by admin"""
    
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
        
        if password1 and len(password1) < 8:
            raise forms.ValidationError("Password must be at least 8 characters long")
        
        return password2
