"""Shared status → badge variant, icon, and filter-chip class mappings."""

from __future__ import annotations

# status_badge.html variants
BadgeVariant = str

APPOINTMENT_STATUS_VARIANTS: dict[str, BadgeVariant] = {
    'pending': 'warning',
    'confirmed': 'success',
    'completed': 'muted',
    'cancelled': 'danger',
}

APPOINTMENT_STATUS_ICONS: dict[str, str] = {
    'pending': 'fa-clock',
    'confirmed': 'fa-circle-check',
    'completed': 'fa-check-double',
    'cancelled': 'fa-ban',
}

DOCUMENT_REQUEST_STATUS_VARIANTS: dict[str, BadgeVariant] = {
    'pending_review': 'warning',
    'pending': 'warning',  # legacy alias in some templates
    'completed': 'muted',
    'rejected': 'danger',
}

DOCUMENT_REQUEST_STATUS_ICONS: dict[str, str] = {
    'pending_review': 'fa-clock',
    'pending': 'fa-clock',
    'completed': 'fa-circle-check',
    'rejected': 'fa-ban',
}

# Calendar day-panel filter chips: (inactive, active) Tailwind class strings.
CALENDAR_FILTER_CHIP_TONES: dict[str, tuple[str, str]] = {
    'all': (
        'bg-white text-gray-600 border-gray-200 hover:border-muted-300 hover:bg-muted-50',
        'bg-muted-100 text-muted-800 border-muted-300 shadow-sm',
    ),
    'pending': (
        'bg-white text-warning-700 border-warning-200 hover:border-warning-300 hover:bg-warning-50',
        'bg-warning-100 text-warning-800 border-warning-300 shadow-sm',
    ),
    'confirmed': (
        'bg-white text-success-700 border-success-200 hover:border-success-300 hover:bg-success-50',
        'bg-success-100 text-success-800 border-success-300 shadow-sm',
    ),
    'completed': (
        'bg-white text-muted-600 border-muted-200 hover:border-muted-300 hover:bg-muted-50',
        'bg-muted-100 text-muted-800 border-muted-300 shadow-sm',
    ),
    'cancelled': (
        'bg-white text-danger-700 border-danger-200 hover:border-danger-300 hover:bg-danger-50',
        'bg-danger-100 text-danger-800 border-danger-300 shadow-sm',
    ),
}


def appointment_status_variant(status: str | None) -> BadgeVariant:
    if not status:
        return 'muted'
    return APPOINTMENT_STATUS_VARIANTS.get(status.strip().lower(), 'muted')


def appointment_status_icon(status: str | None) -> str:
    if not status:
        return ''
    return APPOINTMENT_STATUS_ICONS.get(status.strip().lower(), '')


def document_request_status_variant(status: str | None) -> BadgeVariant:
    if not status:
        return 'muted'
    return DOCUMENT_REQUEST_STATUS_VARIANTS.get(status.strip().lower(), 'muted')


def document_request_status_icon(status: str | None) -> str:
    if not status:
        return ''
    return DOCUMENT_REQUEST_STATUS_ICONS.get(status.strip().lower(), '')


def calendar_filter_chip_class(status_key: str, *, active: bool) -> str:
    inactive, active_cls = CALENDAR_FILTER_CHIP_TONES.get(
        status_key,
        CALENDAR_FILTER_CHIP_TONES['all'],
    )
    return active_cls if active else inactive
