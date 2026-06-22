"""Field mappings for health-forms patient picker prefill (form field → API payload key)."""

import json

PICKER_FIELD_MAPPINGS = {
    'health_profile': {
        'last_name': 'last_name',
        'first_name': 'first_name',
        'middle_name': 'middle_name',
        'permanent_address': 'permanent_address',
        'zip_code': 'zip_code',
        'current_address': 'current_address',
        'place_of_birth': 'place_of_birth',
        'date_of_birth': 'date_of_birth',
        'age': 'age',
        'gender': 'gender',
        'civil_status': 'civil_status',
        'religion': 'religion',
        'citizenship': 'citizenship',
        'email_address': 'email_address',
        'mobile_number': 'mobile_number',
        'telephone_number': 'telephone_number',
        'designation': 'designation',
        'institution_id': 'institution_id',
        'department_college_office': 'department_college_office',
        'course': 'course',
        'year_level': 'year_level',
        'guardian_name': 'guardian_name',
        'guardian_contact': 'guardian_contact',
        'blood_type': 'blood_type',
        'allergies': 'allergies',
        'medical_conditions': 'medical_conditions',
    },
    'patient_chart': {
        'last_name': 'last_name',
        'first_name': 'first_name',
        'middle_name': 'middle_name',
        'address': 'address',
        'date_of_birth': 'date_of_birth',
        'place_of_birth': 'place_of_birth',
        'age': 'age',
        'gender': 'gender',
        'civil_status': 'civil_status',
        'email_address': 'email_address',
        'contact_number': 'contact_number',
        'telephone_number': 'telephone_number',
        'designation': 'designation',
        'department_college_office': 'department_college_office',
        'guardian_name': 'guardian_name',
        'guardian_contact': 'guardian_contact',
    },
    'dental_form': {
        'last_name': 'last_name',
        'first_name': 'first_name',
        'middle_name': 'middle_name',
        'age': 'age',
        'gender': 'gender',
        'civil_status': 'civil_status',
        'address': 'address',
        'date_of_birth': 'date_of_birth',
        'place_of_birth': 'place_of_birth',
        'email_address': 'email_address',
        'contact_number': 'contact_number',
        'telephone_number': 'telephone_number',
        'designation': 'designation',
        'department_college_office': 'department_college_office',
        'guardian_name': 'guardian_name',
        'guardian_contact': 'guardian_contact',
    },
    'dental_services': {
        'last_name': 'last_name',
        'first_name': 'first_name',
        'middle_name': 'middle_name',
        'address': 'address',
        'age': 'age',
        'gender': 'gender',
        'date_of_birth': 'date_of_birth',
        'contact_number': 'contact_number',
        'department': 'department',
    },
    'prescription': {
        'patient_name': 'name',
        'age': 'age',
        'gender': 'gender',
        'address': 'address',
    },
}


def picker_mappings_json(form_key: str) -> str:
    """Return JSON object literal for Alpine fieldMappings config."""
    return json.dumps(PICKER_FIELD_MAPPINGS[form_key])


def picker_field_mappings(form_key: str) -> dict:
    """Return fieldMappings dict for the patient picker Alpine component."""
    return PICKER_FIELD_MAPPINGS[form_key]
