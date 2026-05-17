from .models import Notification
from .settings_service import get_clinic_settings, get_role_features, get_user_preferences
from .utils import is_profile_complete, get_missing_profile_fields


MESSAGE_NOTIFICATION_TYPES = ("direct_message", "announcement_posted")


def notification_context(request):
    """
    Context processor to add unread notification count to all templates
    """
    if request.user.is_authenticated:
        unread_count = Notification.objects.filter(
            user=request.user,
            is_read=False
        ).exclude(
            transaction_type__in=MESSAGE_NOTIFICATION_TYPES
        ).count()

        unread_messages_count = 0
        try:
            from messaging.services import get_unread_conversation_count
            unread_messages_count = get_unread_conversation_count(request.user)
        except Exception:
            unread_messages_count = 0

        return {
            'unread_notifications_count': unread_count,
            'unread_messages_count': unread_messages_count,
        }
    return {
        'unread_notifications_count': 0,
        'unread_messages_count': 0,
    }


def profile_context(request):
    """Add profile completion status to context for authenticated users"""
    if request.user.is_authenticated and request.user.role in ['student', 'staff', 'doctor', 'admin']:
        profile_complete = is_profile_complete(request.user)
        missing_fields = get_missing_profile_fields(request.user) if not profile_complete else []
        
        return {
            'profile_complete': profile_complete,
            'missing_profile_fields': missing_fields,
            'profile_completion_required': not profile_complete
        }
    
    return {
        'profile_complete': True,
        'missing_profile_fields': [],
        'profile_completion_required': False
    }


def clinic_settings_context(request):
    """Expose clinic branding and maintenance flags to all templates."""
    try:
        clinic = get_clinic_settings()
    except Exception:
        return {
            'clinic_name': 'JMCFI Clinic',
            'clinic_logo_url': None,
            'maintenance_mode': False,
            'maintenance_message': '',
        }

    logo_url = clinic.logo.url if clinic.logo else None
    return {
        'clinic_name': clinic.clinic_name,
        'clinic_logo_url': logo_url,
        'maintenance_mode': clinic.maintenance_mode,
        'maintenance_message': clinic.maintenance_message,
    }


def role_features_context(request):
    """Expose per-role feature flags for templates (nav, links)."""
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return {'role_features': {}}
    try:
        return {'role_features': get_role_features(user.role)}
    except ValueError:
        return {'role_features': {}}


def user_preferences_context(request):
    """UI preferences for authenticated users."""
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return {'user_compact_nav': False}
    try:
        return {'user_compact_nav': get_user_preferences(user).compact_nav}
    except Exception:
        return {'user_compact_nav': False}
