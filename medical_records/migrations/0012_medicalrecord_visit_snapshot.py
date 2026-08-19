from django.db import migrations, models


def _full_name(user):
    name = f'{user.first_name or ""} {user.last_name or ""}'.strip()
    return name or (user.email or '')


def _snapshot_for_record(record):
    patient = record.patient
    doctor = record.doctor
    profile = getattr(patient, 'patient_profile', None)
    staff = getattr(doctor, 'staff_profile', None)
    email = (patient.email or '').strip()
    if profile and (profile.contact_email or '').strip():
        email = profile.contact_email.strip()
    return {
        'patient_name': _full_name(patient) or email or '',
        'patient_id': (profile.patient_id if profile else '') or '',
        'email': email,
        'course': (profile.course if profile else '') or '',
        'department': (profile.department if profile else '') or '',
        'doctor_name': _full_name(doctor) or doctor.email or '',
        'doctor_department': (staff.department if staff else '') or '',
        'doctor_specialization': (getattr(staff, 'specialization', '') if staff else '') or '',
    }


def backfill_visit_snapshots(apps, schema_editor):
    MedicalRecord = apps.get_model('medical_records', 'MedicalRecord')
    qs = (
        MedicalRecord.objects.filter(visit_snapshot={})
        .select_related('patient', 'patient__patient_profile', 'doctor', 'doctor__staff_profile')
    )
    for record in qs.iterator():
        record.visit_snapshot = _snapshot_for_record(record)
        record.save(update_fields=['visit_snapshot'])


class Migration(migrations.Migration):

    dependencies = [
        ('medical_records', '0011_medicalrecord_record_date'),
    ]

    operations = [
        migrations.AddField(
            model_name='medicalrecord',
            name='visit_snapshot',
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text='Patient and physician info frozen at record creation.',
            ),
        ),
        migrations.RunPython(backfill_visit_snapshots, migrations.RunPython.noop),
    ]
