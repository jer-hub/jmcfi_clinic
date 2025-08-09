# templatetags/role_tags.py
from django import template

register = template.Library()

@register.filter
def has_role(user, role):
    return user.role == role