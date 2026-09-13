"""Thin shared helpers for analytics views."""

from analytics.services import (
    filters_from_request,
    get_date_range,
    period_presets_for_request,
)

# Private aliases matching prior views.py names (used by sibling modules).
_filters_from_request = filters_from_request
_get_date_range = get_date_range
_period_presets_for_request = period_presets_for_request

__all__ = [
    '_filters_from_request',
    '_get_date_range',
    '_period_presets_for_request',
]
