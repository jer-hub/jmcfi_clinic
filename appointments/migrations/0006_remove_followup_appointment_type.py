from django.db import migrations


def remap_followup_appointments(apps, schema_editor):
    Appointment = apps.get_model('appointments', 'Appointment')
    Appointment.objects.filter(appointment_type='followup').update(appointment_type='consultation')

    AppointmentTypeDefault = apps.get_model('appointments', 'AppointmentTypeDefault')
    AppointmentTypeDefault.objects.filter(appointment_type='followup').delete()


def reverse_remap(apps, schema_editor):
    # Cannot restore deleted type defaults; appointments stay as consultation.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('appointments', '0005_create_default_appointment_type_defaults'),
    ]

    operations = [
        migrations.RunPython(remap_followup_appointments, reverse_remap),
    ]
