"""Central profile-completion policy used across signup/login/profile guards."""

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
    'department',
    'phone',
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
