"""Helpers for recording clinic and role settings changes."""

from __future__ import annotations

import json

from .models import SettingsChangeLog

FIELD_NAME_MAX_LENGTH = SettingsChangeLog._meta.get_field('field_name').max_length


def _serialize_value(value) -> str:
    if value is None:
        return ''
    if isinstance(value, (dict, list)):
        return json.dumps(value, default=str)
    if isinstance(value, bool):
        return 'True' if value else 'False'
    return str(value)


def scoped_field_name(scope: str, field_name: str) -> str:
    """Prefix a field label with an entity scope for grouped settings."""
    scope = (scope or '').strip()
    field_name = (field_name or '').strip()
    merged = ''
    if scope and field_name:
        merged = f'{scope} · {field_name}'
    else:
        merged = scope or field_name
    return merged[:FIELD_NAME_MAX_LENGTH]


def log_settings_change(
    *,
    actor,
    setting_type: str,
    field_name: str,
    old_value='',
    new_value='',
    role: str = '',
) -> None:
    """Create a single settings audit row."""
    SettingsChangeLog.objects.create(
        setting_type=setting_type,
        role=role,
        field_name=field_name,
        old_value=_serialize_value(old_value),
        new_value=_serialize_value(new_value),
        changed_by=actor,
    )


def log_form_field_changes(
    *,
    actor,
    setting_type: str,
    form,
    role: str = '',
    scope: str = '',
) -> int:
    """
    Create audit rows for each changed field on a bound ModelForm.
    Returns the number of log entries created.
    """
    count = 0
    for field_name in form.changed_data:
        old_value = form.initial.get(field_name)
        new_value = form.cleaned_data.get(field_name)
        log_settings_change(
            actor=actor,
            setting_type=setting_type,
            role=role,
            field_name=scoped_field_name(scope, field_name),
            old_value=old_value,
            new_value=new_value,
        )
        count += 1
    return count


def log_boolean_toggle(
    *,
    actor,
    setting_type: str,
    scope: str,
    field_name: str,
    old_value: bool,
    new_value: bool,
    role: str = '',
) -> None:
    log_settings_change(
        actor=actor,
        setting_type=setting_type,
        role=role,
        field_name=scoped_field_name(scope, field_name),
        old_value=old_value,
        new_value=new_value,
    )
