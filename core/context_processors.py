from .models import Notification
from .utils import is_profile_complete, get_missing_profile_fields


def notification_context(request):
    """
    Context processor to add unread notification count to all templates
    """
    if request.user.is_authenticated:
        unread_count = Notification.objects.filter(
            user=request.user,
            is_read=False
        ).count()
        return {
            'unread_notifications_count': unread_count
        }
    return {
        'unread_notifications_count': 0
    }


def profile_context(request):
    """Add profile completion status to context for authenticated users"""
    if request.user.is_authenticated and request.user.role in ['student', 'staff', 'doctor']:
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
