from django.db import migrations, models
from django.utils import timezone


def backfill_record_dates(apps, schema_editor):
    MedicalRecord = apps.get_model('medical_records', 'MedicalRecord')
    Appointment = apps.get_model('appointments', 'Appointment')
    for record in MedicalRecord.objects.filter(record_date__isnull=True).iterator():
        if record.appointment_id:
            apt_date = (
                Appointment.objects.filter(pk=record.appointment_id)
                .values_list('date', flat=True)
                .first()
            )
            if apt_date:
                record.record_date = apt_date
                record.save(update_fields=['record_date'])
                continue
        created = record.created_at
        if timezone.is_aware(created):
            created = timezone.localtime(created)
        record.record_date = created.date()
        record.save(update_fields=['record_date'])


class Migration(migrations.Migration):

    dependencies = [
        ('medical_records', '0010_rename_student_to_patient'),
    ]

    operations = [
        migrations.AddField(
            model_name='medicalrecord',
            name='record_date',
            field=models.DateField(
                blank=True,
                help_text='Calendar date the clinical data was recorded (visit / entry date).',
                null=True,
            ),
        ),
        migrations.RunPython(backfill_record_dates, migrations.RunPython.noop),
    ]
