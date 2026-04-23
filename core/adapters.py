"""
Custom adapters for django-allauth to enforce Google-only authentication
"""
from allauth.core.exceptions import ImmediateHttpResponse
from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.conf import settings
from django.contrib import messages
from django.http import HttpResponseRedirect
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
    
    def _is_allowed_email(self, email):
        allowed_domains = {
            domain.strip().lower()
            for domain in getattr(settings, 'GOOGLE_ALLOWED_DOMAINS', [])
            if domain and domain.strip()
        }
        if not allowed_domains:
            return True
        if not email or '@' not in email:
            return False
        domain = email.rsplit('@', 1)[1].lower()
        return domain in allowed_domains

    def pre_social_login(self, request, sociallogin):
        """
        Block social login early when email/domain is not allowed.
        """
        if sociallogin.account.provider != 'google':
            messages.error(request, 'Only Google authentication is allowed.')
            raise ImmediateHttpResponse(HttpResponseRedirect(reverse('account_login')))

        email = (sociallogin.account.extra_data or {}).get('email') or sociallogin.user.email
        if not self._is_allowed_email(email):
            messages.error(request, 'This Google account is not authorized for this system.')
            raise ImmediateHttpResponse(HttpResponseRedirect(reverse('account_login')))

    def is_open_for_signup(self, request, sociallogin):
        """
        Allow signup via Google OAuth when email policy allows it.
        """
        email = (sociallogin.account.extra_data or {}).get('email') or sociallogin.user.email
        return self._is_allowed_email(email)
    
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
