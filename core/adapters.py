"""
Custom adapters for django-allauth to enforce Google-only authentication
"""
from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.shortcuts import redirect
from django.urls import reverse


class NoPasswordAdapter(DefaultAccountAdapter):
    """
    Adapter to disable password-based authentication
    Forces users to use Google OAuth for login
    """
    
    def is_open_for_signup(self, request):
        """
        Disable manual signup - only allow Google signup
        """
        return False
    
    def get_login_redirect_url(self, request):
        """
        Redirect to dashboard after login
        """
        return reverse('core:dashboard')
    
    def add_message(self, request, level, message_template, message_context=None, extra_tags=''):
        """
        Override to suppress login success messages
        """
        # Suppress all messages from allauth
        pass


class GoogleOnlyAdapter(DefaultSocialAccountAdapter):
    """
    Adapter to handle Google social account authentication
    """
    
    def is_open_for_signup(self, request, sociallogin):
        """
        Allow signup via Google OAuth
        """
        return True
    
    def populate_user(self, request, sociallogin, data):
        """
        Populate user data from Google OAuth response
        """
        user = super().populate_user(request, sociallogin, data)
        
        # Extract and populate user data from Google
        if sociallogin.account.provider == 'google':
            user.first_name = data.get('given_name', '')
            user.last_name = data.get('family_name', '')
            user.email = data.get('email', '')
        
        return user
    
    def save_user(self, request, sociallogin, form=None):
        """
        Save user and ensure role is set before profile creation
        """
        user = super().save_user(request, sociallogin, form)
        
        # Ensure user has a role set (default to student if not set)
        if not user.role or user.role == '':
            user.role = 'student'
            user.save()
        
        return user
    
    def add_message(self, request, level, message_template, message_context=None, extra_tags=''):
        """
        Override to suppress login success messages
        """
        # Suppress all messages from allauth
        pass
