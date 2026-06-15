from django import template

from core.clinical_permissions import (
    can_write_appointments as user_can_write_appointments,
    can_write_dental_records as user_can_write_dental_records,
    can_write_medical_records as user_can_write_medical_records,
    is_staff_clinical_readonly as user_is_staff_clinical_readonly,
)

register = template.Library()


@register.filter
def is_staff_clinical_readonly(user):
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    return user_is_staff_clinical_readonly(user)


@register.filter
def can_write_appointments(user, appointment=None):
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    return user_can_write_appointments(user, appointment)


@register.filter
def can_write_medical_records(user):
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    return user_can_write_medical_records(user)


@register.filter
def can_write_dental_records(user):
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    return user_can_write_dental_records(user)
