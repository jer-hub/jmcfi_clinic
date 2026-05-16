from django.db import migrations
from django.utils import timezone


def backfill_prescription_dates(apps, schema_editor):
    Prescription = apps.get_model('health_forms_services', 'Prescription')
    for rx in Prescription.objects.filter(date__isnull=True).select_related('medical_record'):
        if rx.medical_record_id and rx.medical_record.created_at:
            rx.date = timezone.localtime(rx.medical_record.created_at).date()
        elif rx.created_at:
            rx.date = timezone.localtime(rx.created_at).date()
        else:
            rx.date = timezone.localdate()
        rx.save(update_fields=['date'])


class Migration(migrations.Migration):

    dependencies = [
        ('health_forms_services', '0006_prescription_medical_record'),
    ]

    operations = [
        migrations.RunPython(backfill_prescription_dates, migrations.RunPython.noop),
    ]
