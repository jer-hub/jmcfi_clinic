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

    def _allowed_domains(self):
        return {domain.lower() for domain in get_google_allowed_domains() if domain}

    def _is_allowed_email(self, email):
        allowed_domains = self._allowed_domains()
        if not allowed_domains:
            return True
        if not email or '@' not in email:
            return False
        domain = email.rsplit('@', 1)[1].lower()
        return domain in allowed_domains

    def _domain_rejection_message(self, email):
        """User-facing validation error for Google accounts outside allowed domains."""
        allowed = sorted(self._allowed_domains())
        allowed_display = ', '.join(f'@{d}' for d in allowed) if allowed else ''

        if not email or '@' not in str(email):
            if allowed_display:
                return (
                    f'Sign-in failed: Google did not provide a valid email. '
                    f'Use an institutional account ({allowed_display}).'
                )
            return 'Sign-in failed: Google did not provide a valid email address.'

        email = str(email).strip()
        domain = email.rsplit('@', 1)[1].lower()
        if allowed_display:
            return (
                f'Sign-in failed: {email} is not allowed. '
                f'Only Google accounts from these domains can sign in: {allowed_display}.'
            )
        return (
            f'Sign-in failed: {email} (@{domain}) is not authorized for this system.'
        )

    def _reject_social_login(self, request, message):
        messages.error(request, message)
        raise ImmediateHttpResponse(HttpResponseRedirect(reverse('account_login')))

    def pre_social_login(self, request, sociallogin):
        """
        Block social login early when email/domain is not allowed.
        """
        if sociallogin.account.provider != 'google':
            self._reject_social_login(request, 'Only Google authentication is allowed.')

        email = (sociallogin.account.extra_data or {}).get('email') or sociallogin.user.email
        if not self._is_allowed_email(email):
            self._reject_social_login(request, self._domain_rejection_message(email))

    def is_open_for_signup(self, request, sociallogin):
        """
        Allow signup via Google OAuth when email policy and clinic settings allow it.
        """
        email = (sociallogin.account.extra_data or {}).get('email') or sociallogin.user.email
        if not self._is_allowed_email(email):
            # Defensive: pre_social_login should already reject, but keep signup closed
            # and surface the same validation error if allauth reaches this path.
            self._reject_social_login(request, self._domain_rejection_message(email))
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
