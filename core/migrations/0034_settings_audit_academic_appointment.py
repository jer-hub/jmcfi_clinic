from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0033_patient_profile_zip_code_required'),
    ]

    operations = [
        migrations.AlterField(
            model_name='settingschangelog',
            name='setting_type',
            field=models.CharField(
                choices=[
                    ('clinic', 'Clinic'),
                    ('role', 'Role'),
                    ('academic', 'Academic'),
                    ('appointment', 'Appointments'),
                ],
                max_length=12,
            ),
        ),
    ]
