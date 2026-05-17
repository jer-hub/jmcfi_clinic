from django import template

from core.status_styles import (
    appointment_status_icon,
    appointment_status_variant,
    document_request_status_icon,
    document_request_status_variant,
)

register = template.Library()


@register.filter
def appointment_status_variant_filter(status):
    return appointment_status_variant(status)


@register.filter
def appointment_status_icon_filter(status):
    return appointment_status_icon(status)


@register.filter
def document_request_status_variant_filter(status):
    return document_request_status_variant(status)


@register.inclusion_tag('components/badges/appointment_status_badge.html')
def appointment_status_badge(appointment=None, status=None, label=None, size='md', icon=None):
    resolved_status = status
    display_label = label
    if appointment is not None:
        resolved_status = resolved_status or appointment.status
        if display_label is None:
            display_label = appointment.get_status_display()
    return {
        'badge_label': display_label or '',
        'badge_variant': appointment_status_variant(resolved_status),
        'badge_icon': icon if icon is not None else appointment_status_icon(resolved_status),
        'size': size,
    }


@register.inclusion_tag('components/badges/document_request_status_badge.html')
def document_request_status_badge(
    cert_request=None,
    status=None,
    label=None,
    size='md',
    icon=None,
):
    resolved_status = status
    display_label = label
    if cert_request is not None:
        resolved_status = resolved_status or cert_request.status
        if display_label is None:
            display_label = cert_request.get_status_display()
    return {
        'badge_label': display_label or '',
        'badge_variant': document_request_status_variant(resolved_status),
        'badge_icon': icon if icon is not None else document_request_status_icon(resolved_status),
        'size': size,
    }
