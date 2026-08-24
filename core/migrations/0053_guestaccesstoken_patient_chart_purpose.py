# Generated manually for guest patient chart magic links

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0052_notification_health_form_submitted_completed'),
    ]

    operations = [
        migrations.AlterField(
            model_name='guestaccesstoken',
            name='purpose',
            field=models.CharField(
                choices=[
                    ('appointment', 'Appointment'),
                    ('health_form', 'Health Form'),
                    ('medical_record', 'Medical Record'),
                    ('dental_intake', 'Dental Intake'),
                    ('dental_record', 'Dental Record'),
                    ('patient_chart', 'Patient Chart'),
                ],
                max_length=32,
            ),
        ),
    ]
