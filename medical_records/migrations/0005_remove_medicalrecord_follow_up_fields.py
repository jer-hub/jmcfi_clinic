from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('medical_records', '0004_medicalrecord_status'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='medicalrecord',
            name='follow_up_date',
        ),
        migrations.RemoveField(
            model_name='medicalrecord',
            name='follow_up_required',
        ),
    ]
