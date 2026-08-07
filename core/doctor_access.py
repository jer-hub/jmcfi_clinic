"""Per-user clinical module grants for doctors and staff (Services + Health Forms)."""

from __future__ import annotations

from typing import Iterable

# Stable keys stored on StaffProfile.allowed_clinical_modules
MODULE_APPOINTMENTS = 'appointments'
MODULE_MEDICAL_RECORDS = 'medical_records'
MODULE_DENTAL_RECORDS = 'dental_records'
MODULE_DOCUMENT_REQUEST = 'document_request'
MODULE_PHARMACY = 'pharmacy'
MODULE_HEALTH_PROFILE_FORMS = 'health_profile_forms'
MODULE_DENTAL_HEALTH_FORMS = 'dental_health_forms'
MODULE_PATIENT_CHARTS = 'patient_charts'
MODULE_DENTAL_SERVICES = 'dental_services'
MODULE_PRESCRIPTIONS = 'prescriptions'
MODULE_MANAGE_CONCERN = 'manage_concern'
MODULE_FILES = 'files'

GATED_ROLES = frozenset({'doctor', 'staff'})

# Doctor service catalog (no pharmacy)
DOCTOR_SERVICE_MODULE_CHOICES: list[tuple[str, str]] = [
    (MODULE_APPOINTMENTS, 'Appointments'),
    (MODULE_MEDICAL_RECORDS, 'Medical Records'),
    (MODULE_DENTAL_RECORDS, 'Dental Records'),
    (MODULE_DOCUMENT_REQUEST, 'Document Requests'),
    (MODULE_MANAGE_CONCERN, 'Manage Concern'),
    (MODULE_FILES, 'Clinic Files'),
]

# Staff service catalog (pharmacy instead of document requests)
STAFF_SERVICE_MODULE_CHOICES: list[tuple[str, str]] = [
    (MODULE_APPOINTMENTS, 'Appointments'),
    (MODULE_MEDICAL_RECORDS, 'Medical Records'),
    (MODULE_DENTAL_RECORDS, 'Dental Records'),
    (MODULE_PHARMACY, 'Pharmacy'),
    (MODULE_MANAGE_CONCERN, 'Manage Concern'),
    (MODULE_FILES, 'Clinic Files'),
]

HEALTH_FORM_MODULE_CHOICES: list[tuple[str, str]] = [
    (MODULE_HEALTH_PROFILE_FORMS, 'Health Profile Forms'),
    (MODULE_DENTAL_HEALTH_FORMS, 'Dental Health Forms'),
    (MODULE_PATIENT_CHARTS, 'Patient Charts'),
    (MODULE_DENTAL_SERVICES, 'Dental Services'),
    (MODULE_PRESCRIPTIONS, 'Prescriptions'),
]

# Back-compat aliases used by doctor UI / older imports
SERVICE_MODULE_CHOICES = DOCTOR_SERVICE_MODULE_CHOICES
CLINICAL_MODULE_CHOICES: list[tuple[str, str]] = (
    DOCTOR_SERVICE_MODULE_CHOICES + HEALTH_FORM_MODULE_CHOICES
)
DOCTOR_CLINICAL_MODULE_CHOICES: list[tuple[str, str]] = CLINICAL_MODULE_CHOICES
STAFF_CLINICAL_MODULE_CHOICES: list[tuple[str, str]] = (
    STAFF_SERVICE_MODULE_CHOICES + HEALTH_FORM_MODULE_CHOICES
)

ALL_MODULE_KEYS: frozenset[str] = frozenset(
    key for key, _ in DOCTOR_CLINICAL_MODULE_CHOICES + STAFF_SERVICE_MODULE_CHOICES
)
# Union of service keys used for "any service" nav visibility
SERVICE_MODULE_KEYS: frozenset[str] = frozenset(
    key for key, _ in DOCTOR_SERVICE_MODULE_CHOICES + STAFF_SERVICE_MODULE_CHOICES
)
DOCTOR_SERVICE_MODULE_KEYS: frozenset[str] = frozenset(
    key for key, _ in DOCTOR_SERVICE_MODULE_CHOICES
)
STAFF_SERVICE_MODULE_KEYS: frozenset[str] = frozenset(
    key for key, _ in STAFF_SERVICE_MODULE_CHOICES
)
HEALTH_FORM_MODULE_KEYS: frozenset[str] = frozenset(
    key for key, _ in HEALTH_FORM_MODULE_CHOICES
)

MODULE_LABELS: dict[str, str] = {
    **dict(DOCTOR_CLINICAL_MODULE_CHOICES),
    **dict(STAFF_SERVICE_MODULE_CHOICES),
}

NAMESPACE_TO_MODULE: dict[str, str] = {
    'appointments': MODULE_APPOINTMENTS,
    'medical_records': MODULE_MEDICAL_RECORDS,
    'dental_records': MODULE_DENTAL_RECORDS,
    'document_request': MODULE_DOCUMENT_REQUEST,
    'pharmacy': MODULE_PHARMACY,
    'manage_concern': MODULE_MANAGE_CONCERN,
    'files': MODULE_FILES,
}

_HEALTH_FORM_URL_NAME_PREFIXES: tuple[tuple[str, str], ...] = (
    ('dental_chart_api', MODULE_DENTAL_SERVICES),
    ('dental_services', MODULE_DENTAL_SERVICES),
    ('create_dental_services', MODULE_DENTAL_SERVICES),
    ('edit_dental_services', MODULE_DENTAL_SERVICES),
    ('review_dental_services', MODULE_DENTAL_SERVICES),
    ('delete_dental_services', MODULE_DENTAL_SERVICES),
    ('export_dental_services', MODULE_DENTAL_SERVICES),
    ('dental_forms', MODULE_DENTAL_HEALTH_FORMS),
    ('create_dental_form', MODULE_DENTAL_HEALTH_FORMS),
    ('edit_dental_form', MODULE_DENTAL_HEALTH_FORMS),
    ('review_dental_form', MODULE_DENTAL_HEALTH_FORMS),
    ('delete_dental_form', MODULE_DENTAL_HEALTH_FORMS),
    ('export_dental_form', MODULE_DENTAL_HEALTH_FORMS),
    ('dental_form', MODULE_DENTAL_HEALTH_FORMS),
    ('patient_chart', MODULE_PATIENT_CHARTS),
    ('create_patient_chart', MODULE_PATIENT_CHARTS),
    ('edit_patient_chart', MODULE_PATIENT_CHARTS),
    ('review_patient_chart', MODULE_PATIENT_CHARTS),
    ('delete_patient_chart', MODULE_PATIENT_CHARTS),
    ('export_patient_chart', MODULE_PATIENT_CHARTS),
    ('add_chart_entry', MODULE_PATIENT_CHARTS),
    ('update_chart_entry', MODULE_PATIENT_CHARTS),
    ('delete_chart_entry', MODULE_PATIENT_CHARTS),
    ('prescription', MODULE_PRESCRIPTIONS),
    ('create_prescription', MODULE_PRESCRIPTIONS),
    ('edit_prescription', MODULE_PRESCRIPTIONS),
    ('review_prescription', MODULE_PRESCRIPTIONS),
    ('delete_prescription', MODULE_PRESCRIPTIONS),
    ('export_prescription', MODULE_PRESCRIPTIONS),
    ('add_prescription_item', MODULE_PRESCRIPTIONS),
    ('delete_prescription_item', MODULE_PRESCRIPTIONS),
    ('forms_list', MODULE_HEALTH_PROFILE_FORMS),
    ('manual_entry', MODULE_HEALTH_PROFILE_FORMS),
    ('request_health_profile', MODULE_HEALTH_PROFILE_FORMS),
    ('form_detail', MODULE_HEALTH_PROFILE_FORMS),
    ('edit_form', MODULE_HEALTH_PROFILE_FORMS),
    ('load_form_section', MODULE_HEALTH_PROFILE_FORMS),
    ('submit_for_review', MODULE_HEALTH_PROFILE_FORMS),
    ('review_form', MODULE_HEALTH_PROFILE_FORMS),
    ('delete_form', MODULE_HEALTH_PROFILE_FORMS),
    ('export_form', MODULE_HEALTH_PROFILE_FORMS),
    ('export_health_profile', MODULE_HEALTH_PROFILE_FORMS),
    ('bulk_review', MODULE_HEALTH_PROFILE_FORMS),
)

DOCTOR_MODULE_DENIED = 'doctor_clinical_module'


def clinical_module_choices_for_role(role: str | None) -> list[tuple[str, str]]:
    if role == 'staff':
        return list(STAFF_CLINICAL_MODULE_CHOICES)
    if role == 'doctor':
        return list(DOCTOR_CLINICAL_MODULE_CHOICES)
    return []


def service_module_choices_for_role(role: str | None) -> list[tuple[str, str]]:
    if role == 'staff':
        return list(STAFF_SERVICE_MODULE_CHOICES)
    if role == 'doctor':
        return list(DOCTOR_SERVICE_MODULE_CHOICES)
    return []


def service_module_keys_for_role(role: str | None) -> frozenset[str]:
    if role == 'staff':
        return STAFF_SERVICE_MODULE_KEYS
    if role == 'doctor':
        return DOCTOR_SERVICE_MODULE_KEYS
    return SERVICE_MODULE_KEYS


def normalize_module_list(
    raw: Iterable[str] | None,
    *,
    allowed_keys: frozenset[str] | None = None,
) -> list[str]:
    allowed = allowed_keys if allowed_keys is not None else ALL_MODULE_KEYS
    if not raw:
        return []
    seen: set[str] = set()
    out: list[str] = []
    for item in raw:
        key = str(item or '').strip()
        if key in allowed and key not in seen:
            seen.add(key)
            out.append(key)
    return out


def granted_modules(user) -> set[str]:
    """
    Return granted module keys for doctor/staff.
    Other authenticated roles: all keys (no opt-in gate).
    """
    if not user or not getattr(user, 'is_authenticated', False):
        return set()
    role = getattr(user, 'role', None)
    if role not in GATED_ROLES:
        return set(ALL_MODULE_KEYS)
    try:
        profile = user.staff_profile
    except Exception:
        return set()
    return set(normalize_module_list(getattr(profile, 'allowed_clinical_modules', None)))


def has_clinical_module(user, key: str) -> bool:
    """Doctor/staff need an explicit grant; other roles always True (role gates apply elsewhere)."""
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    if getattr(user, 'role', None) not in GATED_ROLES:
        return True
    return key in granted_modules(user)


# Back-compat alias
doctor_has_module = has_clinical_module


def has_any_service_module(user) -> bool:
    role = getattr(user, 'role', None)
    if role not in GATED_ROLES:
        return True
    keys = service_module_keys_for_role(role)
    return bool(granted_modules(user) & keys)


def has_any_health_form_module(user) -> bool:
    if getattr(user, 'role', None) not in GATED_ROLES:
        return True
    return bool(granted_modules(user) & HEALTH_FORM_MODULE_KEYS)


doctor_has_any_service_module = has_any_service_module
doctor_has_any_health_form_module = has_any_health_form_module


def module_for_health_forms_url_name(url_name: str) -> str | None:
    if not url_name:
        return None
    if url_name in ('search_patients', 'patient_profile_prefill'):
        return None
    for prefix, module in _HEALTH_FORM_URL_NAME_PREFIXES:
        if url_name == prefix or url_name.startswith(prefix):
            return module
    return MODULE_HEALTH_PROFILE_FORMS


def module_for_request(request) -> str | None:
    """Resolve request to a gated clinical module key, or None if not gated."""
    match = getattr(request, 'resolver_match', None)
    if not match:
        return None
    namespace = getattr(match, 'namespace', '') or ''
    url_name = getattr(match, 'url_name', '') or ''

    if namespace in NAMESPACE_TO_MODULE:
        return NAMESPACE_TO_MODULE[namespace]

    if namespace == 'health_forms_services':
        if url_name in ('search_patients', 'patient_profile_prefill'):
            return '__any_health_form__'
        return module_for_health_forms_url_name(url_name)

    return None


def clinical_module_denied_for_request(request) -> str | None:
    """
    For doctor/staff: return denial token if the resolved module is not granted.
    """
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return None
    if getattr(user, 'role', None) not in GATED_ROLES:
        return None

    module = module_for_request(request)
    if module is None:
        return None

    granted = granted_modules(user)
    if module == '__any_health_form__':
        if granted & HEALTH_FORM_MODULE_KEYS:
            return None
        return DOCTOR_MODULE_DENIED

    if module in granted:
        return None
    return DOCTOR_MODULE_DENIED


# Back-compat alias
doctor_denied_module_for_request = clinical_module_denied_for_request


def module_labels_for_keys(keys: Iterable[str]) -> list[str]:
    return [MODULE_LABELS[k] for k in normalize_module_list(keys) if k in MODULE_LABELS]
