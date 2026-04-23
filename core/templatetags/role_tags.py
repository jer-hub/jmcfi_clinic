# templatetags/role_tags.py
from django import template
import re

register = template.Library()

@register.filter
def has_role(user, role):
    return user.role == role


@register.filter
def split_list_items(value):
    """Split multiline/comma-separated text into cleaned non-empty items."""
    if not value:
        return []

    text = str(value)
    parts = re.split(r'[\n,;]+', text)
    return [item.strip() for item in parts if item and item.strip()]

# Navigation helpers
@register.simple_tag(takes_context=True)
def nav_link_class(context, view_name, startswith=False):
    """Return Tailwind classes for active/inactive nav link based on current view name.

    Usage: class="{% nav_link_class 'management:dashboard' %} inline-flex ..."
    Set startswith=True to mark a parent route active for child views.
    """
    request = context.get('request')
    if not request:
        return 'border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700'

    match = getattr(request, 'resolver_match', None)
    curr_name = getattr(match, 'view_name', '') or ''
    is_active = curr_name == view_name or (startswith and curr_name.startswith(view_name))

    return 'border-primary-500 text-gray-900' if is_active else 'border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700'