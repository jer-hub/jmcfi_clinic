from django.db import migrations


def assign_all_doctors_to_unassigned_defaults(apps, schema_editor):
    AppointmentTypeDefault = apps.get_model('appointments', 'AppointmentTypeDefault')
    User = apps.get_model('core', 'User')

    doctor_ids = list(
        User.objects.filter(role__in=['doctor', 'staff'], is_active=True).values_list('pk', flat=True)
    )
    if not doctor_ids:
        return

    for default in AppointmentTypeDefault.objects.all():
        if default.assigned_doctors.count() == 0:
            default.assigned_doctors.set(doctor_ids)


def revert_assign_all_doctors_to_unassigned_defaults(apps, schema_editor):
    AppointmentTypeDefault = apps.get_model('appointments', 'AppointmentTypeDefault')
    User = apps.get_model('core', 'User')

    doctor_ids = set(
        User.objects.filter(role__in=['doctor', 'staff'], is_active=True).values_list('pk', flat=True)
    )
    if not doctor_ids:
        return

    for default in AppointmentTypeDefault.objects.all():
        assigned_ids = set(default.assigned_doctors.values_list('pk', flat=True))
        if assigned_ids and assigned_ids == doctor_ids:
            default.assigned_doctors.clear()


class Migration(migrations.Migration):

    dependencies = [
        ('appointments', '0009_appointment_missed_status'),
    ]

    operations = [
        migrations.RunPython(
            assign_all_doctors_to_unassigned_defaults,
            revert_assign_all_doctors_to_unassigned_defaults,
        ),
    ]
