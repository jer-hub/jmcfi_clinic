from django.db import migrations


DOCTOR_PROFILE_REQUIRED_FIELDS = [
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
    'zip_code',
    'phone',
    'emergency_contact',
    'emergency_phone',
    'department',
    'license_number',
    'ptr_no',
]


def make_doctor_position_admin_managed(apps, schema_editor):
    RoleSettings = apps.get_model('core', 'RoleSettings')
    RoleSettings.objects.filter(role='doctor').update(
        profile_required_fields=DOCTOR_PROFILE_REQUIRED_FIELDS,
    )


def restore_doctor_position_requirement(apps, schema_editor):
    RoleSettings = apps.get_model('core', 'RoleSettings')
    RoleSettings.objects.filter(role='doctor').update(
        profile_required_fields=[
            *DOCTOR_PROFILE_REQUIRED_FIELDS,
            'position',
        ],
    )


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0029_staffprofile_zip_code_and_role_requirements'),
    ]

    operations = [
        migrations.RunPython(
            make_doctor_position_admin_managed,
            restore_doctor_position_requirement,
        ),
    ]
