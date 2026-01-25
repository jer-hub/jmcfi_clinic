from django import forms
from django.contrib.auth import get_user_model
from django.core.validators import RegexValidator
from .models import StudentProfile, StaffProfile

User = get_user_model()


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
