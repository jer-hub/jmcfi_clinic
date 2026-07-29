"""Patient category (student / employee / walk_in) helpers for profiles and clinical forms."""

from __future__ import annotations

PATIENT_CATEGORY_STUDENT = 'student'
PATIENT_CATEGORY_EMPLOYEE = 'employee'
PATIENT_CATEGORY_WALK_IN = 'walk_in'

# Legacy value still accepted by normalize_patient_category.
_LEGACY_GUEST = 'guest'

PATIENT_CATEGORY_CHOICES = [
    (PATIENT_CATEGORY_STUDENT, 'Student'),
    (PATIENT_CATEGORY_EMPLOYEE, 'Employee'),
    (PATIENT_CATEGORY_WALK_IN, 'Walk-in'),
]

# Categories selectable on Google / admin-managed profiles (not walk-in login).
SELECTABLE_PATIENT_CATEGORY_CHOICES = [
    (PATIENT_CATEGORY_STUDENT, 'Student'),
    (PATIENT_CATEGORY_EMPLOYEE, 'Employee'),
]

# Health-form PERSONAL_INFO_SECTIONS keys (or labels used when key is absent).
HEALTH_SECTION_FULL_NAME = 'full_name'
HEALTH_SECTION_BIRTH_DEMOGRAPHICS = 'birth_demographics'
HEALTH_SECTION_CONTACT = 'contact'
HEALTH_SECTION_ADDRESS = 'address'
HEALTH_SECTION_INSTITUTIONAL = 'institutional_details'
HEALTH_SECTION_EMERGENCY = 'emergency_contact'
HEALTH_SECTION_MEDICAL = 'medical_background'

# Sections shown on health/clinical personal-info tabs by category.
HEALTH_FORM_SECTIONS_BY_CATEGORY = {
    PATIENT_CATEGORY_STUDENT: frozenset({
        HEALTH_SECTION_FULL_NAME,
        HEALTH_SECTION_BIRTH_DEMOGRAPHICS,
        HEALTH_SECTION_CONTACT,
        HEALTH_SECTION_ADDRESS,
        HEALTH_SECTION_INSTITUTIONAL,
        HEALTH_SECTION_EMERGENCY,
        HEALTH_SECTION_MEDICAL,
    }),
    PATIENT_CATEGORY_EMPLOYEE: frozenset({
        HEALTH_SECTION_FULL_NAME,
        HEALTH_SECTION_BIRTH_DEMOGRAPHICS,
        HEALTH_SECTION_CONTACT,
        HEALTH_SECTION_ADDRESS,
        HEALTH_SECTION_INSTITUTIONAL,
        HEALTH_SECTION_EMERGENCY,
        HEALTH_SECTION_MEDICAL,
    }),
    PATIENT_CATEGORY_WALK_IN: frozenset({
        HEALTH_SECTION_FULL_NAME,
        HEALTH_SECTION_BIRTH_DEMOGRAPHICS,
        HEALTH_SECTION_CONTACT,
        HEALTH_SECTION_MEDICAL,
    }),
}

# Institutional field names shown on health forms by category.
INSTITUTIONAL_FIELDS_BY_CATEGORY = {
    PATIENT_CATEGORY_STUDENT: (
        'designation',
        'institution_id',
        'department_college_office',
        'course',
        'year_level',
    ),
    PATIENT_CATEGORY_EMPLOYEE: (
        'designation',
        'institution_id',
        'department_college_office',
    ),
    PATIENT_CATEGORY_WALK_IN: (),
}

# Profile institutional fields that are category-dependent.
PROFILE_INSTITUTIONAL_FIELDS = frozenset({'department', 'course', 'year_level'})

# Map section labels (when no key) → canonical section ids for filtering.
SECTION_LABEL_TO_ID = {
    'Full Name': HEALTH_SECTION_FULL_NAME,
    'Birth & Demographics': HEALTH_SECTION_BIRTH_DEMOGRAPHICS,
    'Contact Information': HEALTH_SECTION_CONTACT,
    'Contact': HEALTH_SECTION_CONTACT,
    'Address': HEALTH_SECTION_ADDRESS,
    'Institutional Details': HEALTH_SECTION_INSTITUTIONAL,
    'Institution': HEALTH_SECTION_INSTITUTIONAL,
    'Designation': HEALTH_SECTION_INSTITUTIONAL,
    'Emergency Contact': HEALTH_SECTION_EMERGENCY,
    'In Case of Emergency, Please Contact': HEALTH_SECTION_EMERGENCY,
    'Medical & Health Information': HEALTH_SECTION_MEDICAL,
    'Name & Demographics': HEALTH_SECTION_FULL_NAME,
    'Address & Birth': HEALTH_SECTION_ADDRESS,
}


def normalize_patient_category(category: str | None) -> str:
    """Return a known category, defaulting to student."""
    value = (category or '').strip().lower()
    if value == 'patient':
        return PATIENT_CATEGORY_STUDENT
    if value == _LEGACY_GUEST:
        return PATIENT_CATEGORY_WALK_IN
    if value in {
        PATIENT_CATEGORY_STUDENT,
        PATIENT_CATEGORY_EMPLOYEE,
        PATIENT_CATEGORY_WALK_IN,
    }:
        return value
    return PATIENT_CATEGORY_STUDENT


def category_to_designation(category: str | None) -> str:
    """Map patient_category → clinical form designation value."""
    return normalize_patient_category(category)


def designation_to_category(designation: str | None) -> str:
    """Map clinical designation → patient category (staff/doctor → employee)."""
    value = (designation or '').strip().lower()
    if value in {'staff', 'doctor', 'employee'}:
        return PATIENT_CATEGORY_EMPLOYEE
    if value in {_LEGACY_GUEST, PATIENT_CATEGORY_WALK_IN}:
        return PATIENT_CATEGORY_WALK_IN
    return PATIENT_CATEGORY_STUDENT


def health_form_sections_for_category(category: str | None) -> frozenset[str]:
    return HEALTH_FORM_SECTIONS_BY_CATEGORY[normalize_patient_category(category)]


def institutional_fields_for_category(category: str | None) -> tuple[str, ...]:
    return INSTITUTIONAL_FIELDS_BY_CATEGORY[normalize_patient_category(category)]


def section_id_from_spec(section: dict) -> str | None:
    """Resolve a PERSONAL_INFO_SECTIONS-style dict to a canonical section id."""
    key = section.get('key')
    if key:
        return str(key)
    label = section.get('label')
    if label:
        return SECTION_LABEL_TO_ID.get(str(label))
    return None


def required_profile_fields_for_category(
    base_required: list[str] | set[str],
    category: str | None,
) -> set[str]:
    """
    Adjust patient profile required fields by category.

    - student / employee: keep department from base when present
    - walk_in: drop department, course, year_level
    - employee: drop course, year_level from required (form still clears them)
    """
    required = {normalize_profile_field_name(f) for f in base_required}
    category = normalize_patient_category(category)

    if category == PATIENT_CATEGORY_WALK_IN:
        required -= PROFILE_INSTITUTIONAL_FIELDS
    elif category == PATIENT_CATEGORY_EMPLOYEE:
        required -= {'course', 'year_level'}
        # department stays if it was in base policy
    # student: keep base as-is (department required; course/year enforced in form clean)
    return required


def normalize_profile_field_name(field: str) -> str:
    if field == 'student_id':
        return 'patient_id'
    return field


def category_from_profile(profile) -> str:
    """Read patient_category from a PatientProfile-like object."""
    if not profile:
        return PATIENT_CATEGORY_STUDENT
    return normalize_patient_category(getattr(profile, 'patient_category', None))


def is_walk_in_category(category: str | None) -> bool:
    return normalize_patient_category(category) == PATIENT_CATEGORY_WALK_IN
