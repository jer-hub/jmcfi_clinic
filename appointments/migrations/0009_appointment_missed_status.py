from django.db import migrations, models
from django.db.models import Q
from django.utils import timezone


def mark_past_pending_as_missed(apps, schema_editor):
    Appointment = apps.get_model('appointments', 'Appointment')
    now = timezone.localtime()
    past_slot = Q(date__lt=now.date()) | Q(date=now.date(), time__lt=now.time())
    Appointment.objects.filter(status='pending').filter(past_slot).update(status='missed')


class Migration(migrations.Migration):

    dependencies = [
        ('appointments', '0008_rename_student_to_patient'),
    ]

    operations = [
        migrations.AlterField(
            model_name='appointment',
            name='status',
            field=models.CharField(
                choices=[
                    ('pending', 'Pending'),
                    ('confirmed', 'Confirmed'),
                    ('completed', 'Completed'),
                    ('missed', 'Missed'),
                    ('cancelled', 'Cancelled'),
                ],
                default='pending',
                max_length=20,
            ),
        ),
        migrations.RunPython(mark_past_pending_as_missed, migrations.RunPython.noop),
    ]
