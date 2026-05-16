from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('medical_records', '0003_remove_medicalrecord_prescription'),
    ]

    operations = [
        migrations.AddField(
            model_name='medicalrecord',
            name='status',
            field=models.CharField(
                choices=[('pending', 'Pending'), ('completed', 'Completed')],
                default='completed',
                help_text='Clinical completion: pending until staff marks the encounter finalized.',
                max_length=20,
            ),
        ),
    ]
