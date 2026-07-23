from django.db import migrations


def remove_blood_type_requirement(apps, schema_editor):
    RoleSettings = apps.get_model('core', 'RoleSettings')
    for role in RoleSettings.objects.filter(role__in=['patient', 'student']):
        fields = list(role.profile_required_fields or [])
        if 'blood_type' not in fields:
            continue
        role.profile_required_fields = [field for field in fields if field != 'blood_type']
        role.save(update_fields=['profile_required_fields'])


def restore_blood_type_requirement(apps, schema_editor):
    RoleSettings = apps.get_model('core', 'RoleSettings')
    for role in RoleSettings.objects.filter(role__in=['patient', 'student']):
        fields = list(role.profile_required_fields or [])
        if 'blood_type' in fields:
            continue
        fields.append('blood_type')
        role.profile_required_fields = fields
        role.save(update_fields=['profile_required_fields'])


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0035_expand_settings_change_field_name'),
    ]

    operations = [
        migrations.RunPython(
            remove_blood_type_requirement,
            restore_blood_type_requirement,
        ),
    ]
