from django.db import migrations, models


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
    'zip_code',
    'phone',
    'emergency_contact',
    'emergency_phone',
    'department',
]

ADMIN_PROFILE_REQUIRED_FIELDS = list(STAFF_PROFILE_REQUIRED_FIELDS)

DOCTOR_PROFILE_REQUIRED_FIELDS = [
    *STAFF_PROFILE_REQUIRED_FIELDS,
    'position',
    'license_number',
    'ptr_no',
]


def apply_staff_role_profile_requirements(apps, schema_editor):
    RoleSettings = apps.get_model('core', 'RoleSettings')
    RoleSettings.objects.filter(role='staff').update(
        profile_required_fields=STAFF_PROFILE_REQUIRED_FIELDS,
    )
    RoleSettings.objects.filter(role='admin').update(
        profile_required_fields=ADMIN_PROFILE_REQUIRED_FIELDS,
    )
    RoleSettings.objects.filter(role='doctor').update(
        profile_required_fields=DOCTOR_PROFILE_REQUIRED_FIELDS,
    )


def revert_staff_role_profile_requirements(apps, schema_editor):
    RoleSettings = apps.get_model('core', 'RoleSettings')
    RoleSettings.objects.filter(role='staff').update(
        profile_required_fields=[
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
        ],
    )
    RoleSettings.objects.filter(role='admin').update(
        profile_required_fields=[
            'first_name',
            'last_name',
            'staff_id',
            'phone',
        ],
    )
    RoleSettings.objects.filter(role='doctor').update(
        profile_required_fields=[
            'first_name',
            'last_name',
            'staff_id',
            'department',
            'position',
            'phone',
            'license_number',
            'ptr_no',
        ],
    )


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0028_patientprofile_zip_code'),
    ]

    operations = [
        migrations.AddField(
            model_name='staffprofile',
            name='zip_code',
            field=models.CharField(blank=True, default='', max_length=10),
        ),
        migrations.RunPython(
            apply_staff_role_profile_requirements,
            revert_staff_role_profile_requirements,
        ),
    ]
