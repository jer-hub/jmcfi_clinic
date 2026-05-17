"""Helpers for recording clinic and role settings changes."""

from __future__ import annotations

import json

from .models import SettingsChangeLog


def _serialize_value(value) -> str:
    if value is None:
        return ''
    if isinstance(value, (dict, list)):
        return json.dumps(value, default=str)
    return str(value)


def log_form_field_changes(*, actor, setting_type: str, form, role: str = '') -> int:
    """
    Create audit rows for each changed field on a bound ModelForm.
    Returns the number of log entries created.
    """
    count = 0
    for field_name in form.changed_data:
        old_value = form.initial.get(field_name)
        new_value = form.cleaned_data.get(field_name)
        SettingsChangeLog.objects.create(
            setting_type=setting_type,
            role=role,
            field_name=field_name,
            old_value=_serialize_value(old_value),
            new_value=_serialize_value(new_value),
            changed_by=actor,
        )
        count += 1
    return count
