from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('appointments', '0009_appointment_missed_status'),
        ('document_request', '0011_rename_student_to_patient'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='documentrequest',
            name='uniq_pending_document_request_per_type',
        ),
        migrations.AddField(
            model_name='documentrequest',
            name='appointment',
            field=models.ForeignKey(
                blank=True,
                help_text='Completed visit this certificate request is tied to, when created from an appointment.',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='document_requests',
                to='appointments.appointment',
            ),
        ),
        migrations.AddConstraint(
            model_name='documentrequest',
            constraint=models.UniqueConstraint(
                condition=models.Q(('appointment__isnull', True), ('status', 'pending_review')),
                fields=('patient', 'document_type'),
                name='uniq_pending_document_request_per_type',
            ),
        ),
        migrations.AddConstraint(
            model_name='documentrequest',
            constraint=models.UniqueConstraint(
                condition=models.Q(('appointment__isnull', False), ('status', 'pending_review')),
                fields=('patient', 'document_type', 'appointment'),
                name='uniq_pending_document_request_per_appointment',
            ),
        ),
    ]
