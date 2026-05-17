"""Role feature flag checks for views and middleware."""

from __future__ import annotations

from .settings_service import get_role_features
from .utils import role_home_url_name

# App namespace -> RoleSettings boolean field
NAMESPACE_FEATURE_FLAGS: dict[str, str] = {
    'analytics': 'can_access_analytics',
    'feedback': 'can_submit_feedback',
    'messaging': 'can_use_messaging',
    'health_tips': 'show_health_tips_nav',
}

# (namespace, url_name) -> flag (appointment booking is not whole-app)
URL_FEATURE_FLAGS: dict[tuple[str, str], str] = {
    ('appointments', 'schedule_appointment'): 'can_book_appointments',
}

FEATURE_DENIED_MESSAGES: dict[str, str] = {
    'can_access_analytics': 'Analytics is not enabled for your role.',
    'can_submit_feedback': 'Feedback is not enabled for your role.',
    'can_use_messaging': 'Messaging is not enabled for your role.',
    'show_health_tips_nav': 'Health tips are not enabled for your role.',
    'can_book_appointments': 'Appointment booking is not enabled for your role.',
}


def get_denied_feature_for_request(request) -> str | None:
    """Return the feature flag name blocking this request, or None if allowed."""
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return None

    match = getattr(request, 'resolver_match', None)
    if not match:
        return None

    namespace = getattr(match, 'namespace', '') or ''
    url_name = getattr(match, 'url_name', '') or ''

    try:
        features = get_role_features(user.role)
    except ValueError:
        return None

    url_flag = URL_FEATURE_FLAGS.get((namespace, url_name))
    if url_flag and not features.get(url_flag, False):
        return url_flag

    namespace_flag = NAMESPACE_FEATURE_FLAGS.get(namespace)
    if namespace_flag and not features.get(namespace_flag, False):
        return namespace_flag

    return None


def feature_denied_message(flag_name: str) -> str:
    return FEATURE_DENIED_MESSAGES.get(flag_name, 'This feature is not enabled for your role.')


def feature_denied_redirect_target(user):
    return role_home_url_name(user)
