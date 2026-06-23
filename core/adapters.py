"""
Custom adapters for django-allauth to enforce Google-only authentication
"""
from allauth.core.exceptions import ImmediateHttpResponse
from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.urls import reverse

from core.settings_service import get_clinic_settings, get_google_allowed_domains
from core.utils import normalize_person_name


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
        from core.utils import role_home_url
        if request.user.is_authenticated:
            return role_home_url(request.user)
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
        allowed_domains = {domain.lower() for domain in get_google_allowed_domains()}
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
        Allow signup via Google OAuth when email policy and clinic settings allow it.
        """
        email = (sociallogin.account.extra_data or {}).get('email') or sociallogin.user.email
        if not self._is_allowed_email(email):
            return False
        if sociallogin.is_existing:
            return True
        return get_clinic_settings().allow_patient_self_signup
    
    def populate_user(self, request, sociallogin, data):
        """
        Populate user data from Google OAuth response
        """
        user = super().populate_user(request, sociallogin, data)
        
        # Extract and populate user data from Google
        if sociallogin.account.provider == 'google':
            user.first_name = normalize_person_name(data.get('given_name', ''))
            user.last_name = normalize_person_name(data.get('family_name', ''))
            user.email = data.get('email', '')
        
        return user
    
    def save_user(self, request, sociallogin, form=None):
        """
        Save user and ensure role is set before profile creation
        """
        user = super().save_user(request, sociallogin, form)
        
        # Ensure user has a role set (default to patient if not set)
        if not user.role or user.role == '':
            from .roles import ROLE_PATIENT
            user.role = ROLE_PATIENT
            user.save()

        return user
    
    def add_message(self, request, level, message_template, message_context=None, extra_tags=''):
        """
        Override to suppress login success messages
        """
        # Suppress all messages from allauth
        pass
