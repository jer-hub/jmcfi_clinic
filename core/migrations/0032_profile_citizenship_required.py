from django.db import migrations


PATIENT_PROFILE_REQUIRED_FIELDS = [
    'first_name',
    'last_name',
    'patient_id',
    'middle_name',
    'gender',
    'civil_status',
    'religion',
    'citizenship',
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

STAFF_PROFILE_REQUIRED_FIELDS = [
    'first_name',
    'last_name',
    'staff_id',
    'middle_name',
    'gender',
    'civil_status',
    'religion',
    'citizenship',
    'date_of_birth',
    'place_of_birth',
    'age',
    'address',
    'zip_code',
    'phone',
    'emergency_contact',
    'emergency_phone',
    'department',
]

ADMIN_PROFILE_REQUIRED_FIELDS = list(STAFF_PROFILE_REQUIRED_FIELDS)

DOCTOR_PROFILE_REQUIRED_FIELDS = [
    *STAFF_PROFILE_REQUIRED_FIELDS,
    'license_number',
    'ptr_no',
]


def apply_citizenship_required_fields(apps, schema_editor):
    RoleSettings = apps.get_model('core', 'RoleSettings')
    RoleSettings.objects.filter(role='patient').update(
        profile_required_fields=PATIENT_PROFILE_REQUIRED_FIELDS,
    )
    RoleSettings.objects.filter(role='staff').update(
        profile_required_fields=STAFF_PROFILE_REQUIRED_FIELDS,
    )
    RoleSettings.objects.filter(role='admin').update(
        profile_required_fields=ADMIN_PROFILE_REQUIRED_FIELDS,
    )
    RoleSettings.objects.filter(role='doctor').update(
        profile_required_fields=DOCTOR_PROFILE_REQUIRED_FIELDS,
    )


def revert_citizenship_required_fields(apps, schema_editor):
    RoleSettings = apps.get_model('core', 'RoleSettings')

    def without_citizenship(fields):
        return [field for field in fields if field != 'citizenship']

    RoleSettings.objects.filter(role='patient').update(
        profile_required_fields=without_citizenship(PATIENT_PROFILE_REQUIRED_FIELDS),
    )
    RoleSettings.objects.filter(role='staff').update(
        profile_required_fields=without_citizenship(STAFF_PROFILE_REQUIRED_FIELDS),
    )
    RoleSettings.objects.filter(role='admin').update(
        profile_required_fields=without_citizenship(ADMIN_PROFILE_REQUIRED_FIELDS),
    )
    RoleSettings.objects.filter(role='doctor').update(
        profile_required_fields=without_citizenship(DOCTOR_PROFILE_REQUIRED_FIELDS),
    )


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0031_profile_religion_required'),
    ]

    operations = [
        migrations.RunPython(
            apply_citizenship_required_fields,
            revert_citizenship_required_fields,
        ),
    ]
