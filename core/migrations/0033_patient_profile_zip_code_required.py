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
    'zip_code',
    'phone',
    'emergency_contact',
    'emergency_phone',
    'department',
    'blood_type',
]


def apply_patient_zip_code_requirement(apps, schema_editor):
    RoleSettings = apps.get_model('core', 'RoleSettings')
    RoleSettings.objects.filter(role='patient').update(
        profile_required_fields=PATIENT_PROFILE_REQUIRED_FIELDS,
    )


def revert_patient_zip_code_requirement(apps, schema_editor):
    RoleSettings = apps.get_model('core', 'RoleSettings')
    RoleSettings.objects.filter(role='patient').update(
        profile_required_fields=[
            field for field in PATIENT_PROFILE_REQUIRED_FIELDS if field != 'zip_code'
        ],
    )


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0032_profile_citizenship_required'),
    ]

    operations = [
        migrations.RunPython(
            apply_patient_zip_code_requirement,
            revert_patient_zip_code_requirement,
        ),
    ]
