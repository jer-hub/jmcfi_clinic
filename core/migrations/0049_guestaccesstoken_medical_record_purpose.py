# Generated manually for guest medical-record magic links

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0048_notification_health_form_incomplete'),
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
                ],
                max_length=32,
            ),
        ),
    ]
