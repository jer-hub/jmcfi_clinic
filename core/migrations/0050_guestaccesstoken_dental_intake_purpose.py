# Generated manually for guest dental intake magic links

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0049_guestaccesstoken_medical_record_purpose'),
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
                ],
                max_length=32,
            ),
        ),
    ]
