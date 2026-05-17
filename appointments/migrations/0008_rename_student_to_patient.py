# Generated manually for student → patient rename (Phase 1)

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('appointments', '0007_alter_appointment_appointment_type_and_more'),
        ('core', '0019_rename_student_to_patient'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RenameField(
            model_name='appointment',
            old_name='student',
            new_name='patient',
        ),
        migrations.AlterField(
            model_name='appointment',
            name='patient',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='patient_appointments',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
