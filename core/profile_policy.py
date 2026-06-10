"""Central profile-completion policy used across signup/login/profile guards."""

import re

# E.164 Philippine mobile — must match form validation (core/forms.py).
PH_PROFILE_E164_RE = re.compile(r'^\+63\d{10}$')

PHONE_PROFILE_FIELDS = frozenset({'phone', 'emergency_phone', 'telephone_number'})

USER_PROFILE_FIELDS = frozenset({'first_name', 'last_name'})

# Patient profile fields required after Google signup before service access.
PATIENT_PROFILE_REQUIRED_FIELDS = [
    'first_name',
    'last_name',
    'patient_id',
    'middle_name',
    'gender',
    'civil_status',
    'date_of_birth',
    'place_of_birth',
    'age',
    'address',
    'phone',
    'emergency_contact',
    'emergency_phone',
    'department',
    'blood_type',
]

# Deprecated alias — settings JSON may still list student_id until migrated
STUDENT_PROFILE_REQUIRED_FIELDS = PATIENT_PROFILE_REQUIRED_FIELDS

# Staff profile fields required before service access.
STAFF_PROFILE_REQUIRED_FIELDS = [
    'first_name',
    'last_name',
    'staff_id',
    'middle_name',
    'gender',
    'civil_status',
    'date_of_birth',
    'place_of_birth',
    'age',
    'address',
    'phone',
    'emergency_contact',
    'emergency_phone',
    'department',
]

# Admin profile fields required before service access.
ADMIN_PROFILE_REQUIRED_FIELDS = [
    'first_name',
    'last_name',
    'staff_id',
    'phone',
]

# Doctor profile fields required before service access.
DOCTOR_PROFILE_REQUIRED_FIELDS = [
    'first_name',
    'last_name',
    'staff_id',
    'department',
    'position',
    'phone',
    'license_number',
    'ptr_no',
]


def normalize_profile_field_name(field: str) -> str:
    """Map legacy settings keys to model field names."""
    if field == 'student_id':
        return 'patient_id'
    return field


def is_profile_field_value_complete(field: str, value) -> bool:
    """True when a required profile field has a meaningful saved value."""
    if value is None:
        return False
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return False
        if field in PHONE_PROFILE_FIELDS:
            return bool(PH_PROFILE_E164_RE.fullmatch(stripped))
        return True
    return True


def profile_fields_required_for_role(role: str) -> set[str]:
    """Profile model field names required for *role* (excludes first/last name on User)."""
    from .settings_service import get_profile_required_fields

    required = set()
    for field in get_profile_required_fields(role):
        if field in USER_PROFILE_FIELDS:
            continue
        required.add(normalize_profile_field_name(field))
    return required


def apply_profile_required_fields_to_form(form, role: str | None) -> None:
    """Set ModelForm field.required flags from role policy."""
    if not role:
        return
    from .roles import normalize_role

    required = profile_fields_required_for_role(normalize_role(role))
    for field_name in list(form.fields.keys()):
        form.fields[field_name].required = field_name in required
    sync_widget_required_attrs(form)


def sync_widget_required_attrs(form) -> None:
    """Align HTML5 required/pattern attrs with Django field.required flags."""
    phone_fields = PHONE_PROFILE_FIELDS
    for name, field in form.fields.items():
        if field.required:
            field.widget.attrs['required'] = True
        else:
            field.widget.attrs.pop('required', None)
            field.widget.attrs.pop('aria-required', None)
            if name in phone_fields:
                # Optional phones must not block submit with +63 prefill or pattern.
                field.widget.attrs.pop('pattern', None)
                field.widget.attrs.pop('minlength', None)
                field.widget.attrs.pop('maxlength', None)
