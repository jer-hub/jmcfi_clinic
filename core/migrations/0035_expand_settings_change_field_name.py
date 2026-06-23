from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0034_settings_audit_academic_appointment'),
    ]

    operations = [
        migrations.AlterField(
            model_name='settingschangelog',
            name='field_name',
            field=models.CharField(max_length=255),
        ),
    ]
