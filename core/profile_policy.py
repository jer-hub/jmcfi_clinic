"""Central profile-completion policy used across signup/login/profile guards."""

# Student profile fields required after Google signup before service access.
STUDENT_PROFILE_REQUIRED_FIELDS = [
    'student_id',
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

# Staff profile fields required before service access.
STAFF_PROFILE_REQUIRED_FIELDS = [
    'staff_id',
    'department',
    'phone',
]

# Doctor profile fields required before service access.
DOCTOR_PROFILE_REQUIRED_FIELDS = [
    'staff_id',
    'department',
    'position',
    'phone',
    'license_number',
    'ptr_no',
]
