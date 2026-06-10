from django.db import migrations


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
    'phone',
    'emergency_contact',
    'emergency_phone',
    'department',
]


def apply_staff_contact_required_fields(apps, schema_editor):
    RoleSettings = apps.get_model('core', 'RoleSettings')
    RoleSettings.objects.filter(role='staff').update(
        profile_required_fields=STAFF_PROFILE_REQUIRED_FIELDS,
    )


def revert_staff_contact_required_fields(apps, schema_editor):
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
            'department',
            'phone',
        ],
    )


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0025_staff_profile_demographics_required'),
    ]

    operations = [
        migrations.RunPython(
            apply_staff_contact_required_fields,
            revert_staff_contact_required_fields,
        ),
    ]
