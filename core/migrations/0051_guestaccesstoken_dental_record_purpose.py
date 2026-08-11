# Generated manually for guest dental record (results) magic links

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0050_guestaccesstoken_dental_intake_purpose'),
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
                ],
                max_length=32,
            ),
        ),
    ]
