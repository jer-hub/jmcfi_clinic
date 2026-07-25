from django.db import migrations


def remove_middle_name_requirement(apps, schema_editor):
    RoleSettings = apps.get_model('core', 'RoleSettings')
    for role in RoleSettings.objects.all():
        fields = list(role.profile_required_fields or [])
        if 'middle_name' not in fields:
            continue
        role.profile_required_fields = [field for field in fields if field != 'middle_name']
        role.save(update_fields=['profile_required_fields'])


def restore_middle_name_requirement(apps, schema_editor):
    RoleSettings = apps.get_model('core', 'RoleSettings')
    for role in RoleSettings.objects.all():
        fields = list(role.profile_required_fields or [])
        if 'middle_name' in fields:
            continue
        # Insert after id-like fields when present for stable readability.
        insert_at = 0
        for marker in ('patient_id', 'student_id', 'staff_id', 'last_name'):
            if marker in fields:
                insert_at = fields.index(marker) + 1
                break
        fields.insert(insert_at, 'middle_name')
        role.profile_required_fields = fields
        role.save(update_fields=['profile_required_fields'])


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0036_patient_blood_type_optional'),
    ]

    operations = [
        migrations.RunPython(
            remove_middle_name_requirement,
            restore_middle_name_requirement,
        ),
    ]
