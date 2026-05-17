# Generated manually for student → patient rename (Phase 1)

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def migrate_user_roles_forward(apps, schema_editor):
    User = apps.get_model('core', 'User')
    User.objects.filter(role='student').update(role='patient')


def migrate_user_roles_reverse(apps, schema_editor):
    User = apps.get_model('core', 'User')
    User.objects.filter(role='patient').update(role='student')


def migrate_role_settings_forward(apps, schema_editor):
    RoleSettings = apps.get_model('core', 'RoleSettings')
    for rs in RoleSettings.objects.filter(role='student'):
        fields = list(rs.profile_required_fields or [])
        rs.profile_required_fields = [
            'patient_id' if f == 'student_id' else f for f in fields
        ]
        rs.role = 'patient'
        rs.save(update_fields=['role', 'profile_required_fields'])


def migrate_role_settings_reverse(apps, schema_editor):
    RoleSettings = apps.get_model('core', 'RoleSettings')
    for rs in RoleSettings.objects.filter(role='patient'):
        fields = list(rs.profile_required_fields or [])
        rs.profile_required_fields = [
            'student_id' if f == 'patient_id' else f for f in fields
        ]
        rs.role = 'student'
        rs.save(update_fields=['role', 'profile_required_fields'])


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0018_settings_change_log'),
    ]

    operations = [
        migrations.RunPython(migrate_user_roles_forward, migrate_user_roles_reverse),
        migrations.RenameModel(
            old_name='StudentProfile',
            new_name='PatientProfile',
        ),
        migrations.RenameField(
            model_name='patientprofile',
            old_name='student_id',
            new_name='patient_id',
        ),
        migrations.AlterField(
            model_name='patientprofile',
            name='user',
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='patient_profile',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name='patientprofile',
            name='profile_image',
            field=models.ImageField(
                blank=True,
                help_text='Profile photo',
                null=True,
                upload_to='profiles/patients/',
            ),
        ),
        migrations.RenameField(
            model_name='clinicsettings',
            old_name='allow_student_self_signup',
            new_name='allow_patient_self_signup',
        ),
        migrations.AlterField(
            model_name='clinicsettings',
            name='allow_patient_self_signup',
            field=models.BooleanField(
                default=True,
                help_text='Allow new patients to register via Google OAuth.',
            ),
        ),
        migrations.RunPython(migrate_role_settings_forward, migrate_role_settings_reverse),
        migrations.AlterField(
            model_name='user',
            name='role',
            field=models.CharField(
                choices=[
                    ('admin', 'Admin'),
                    ('doctor', 'Doctor'),
                    ('staff', 'Staff'),
                    ('patient', 'Patient'),
                ],
                default='patient',
                max_length=10,
            ),
        ),
        migrations.AlterField(
            model_name='rolesettings',
            name='role',
            field=models.CharField(
                choices=[
                    ('admin', 'Admin'),
                    ('doctor', 'Doctor'),
                    ('staff', 'Staff'),
                    ('patient', 'Patient'),
                ],
                max_length=10,
                unique=True,
            ),
        ),
    ]
