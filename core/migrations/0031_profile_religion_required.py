from django.db import migrations


PATIENT_PROFILE_REQUIRED_FIELDS = [
    'first_name',
    'last_name',
    'patient_id',
    'middle_name',
    'gender',
    'civil_status',
    'religion',
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


def apply_religion_required_fields(apps, schema_editor):
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


def revert_religion_required_fields(apps, schema_editor):
    RoleSettings = apps.get_model('core', 'RoleSettings')

    def without_religion(fields):
        return [field for field in fields if field != 'religion']

    RoleSettings.objects.filter(role='patient').update(
        profile_required_fields=without_religion(PATIENT_PROFILE_REQUIRED_FIELDS),
    )
    RoleSettings.objects.filter(role='staff').update(
        profile_required_fields=without_religion(STAFF_PROFILE_REQUIRED_FIELDS),
    )
    RoleSettings.objects.filter(role='admin').update(
        profile_required_fields=without_religion(ADMIN_PROFILE_REQUIRED_FIELDS),
    )
    RoleSettings.objects.filter(role='doctor').update(
        profile_required_fields=without_religion(DOCTOR_PROFILE_REQUIRED_FIELDS),
    )


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0030_doctor_position_admin_managed'),
    ]

    operations = [
        migrations.RunPython(
            apply_religion_required_fields,
            revert_religion_required_fields,
        ),
    ]
