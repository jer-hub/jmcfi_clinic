from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter
def format_person_name(user, profile=None):
    """Title-cased full name (first, middle, last) for any user/profile."""
    if not user:
        return ''
    from core.utils import person_display_name

    return person_display_name(user, profile)


@register.filter
def format_student_name(user):
    """Title-cased student display name (first, middle, last)."""
    if not user:
        return ''
    from core.utils import student_display_name

    from core.roles import ROLE_PATIENT, role_matches

    if role_matches(getattr(user, 'role', None), ROLE_PATIENT):
        return student_display_name(user)
    from core.utils import person_display_name

    return person_display_name(user)


@register.filter
def format_audit_meta(value):
    """Render an audit metadata dict as readable key-value badges."""
    if not value or not isinstance(value, dict):
        return '—'

    parts = []
    for key, val in value.items():
        label = key.replace('_', ' ').title()
        display = str(val)
        if isinstance(val, bool):
            display = 'Yes' if val else 'No'
        parts.append(
            f'<span class="inline-flex items-center px-2 py-0.5 rounded text-xs '
            f'font-medium bg-gray-100 text-gray-700 mr-1 mb-1">'
            f'<span class="font-semibold mr-1">{label}:</span> {display}</span>'
        )
    return mark_safe(''.join(parts))
