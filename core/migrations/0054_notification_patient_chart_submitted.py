# Patient chart submitted notification type + backfill existing guest submits

from django.db import migrations, models


def forwards_backfill(apps, schema_editor):
    Notification = apps.get_model('core', 'Notification')
    Notification.objects.filter(
        title='Guest patient chart submitted',
        transaction_type='general_announcement',
        related_id__isnull=False,
    ).update(transaction_type='patient_chart_submitted')


def backwards_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0053_guestaccesstoken_patient_chart_purpose'),
    ]

    operations = [
        migrations.AlterField(
            model_name='notification',
            name='transaction_type',
            field=models.CharField(
                blank=True,
                choices=[
                    ('appointment_reminder', 'Appointment Reminder'),
                    ('appointment_confirmed', 'Appointment Confirmed'),
                    ('appointment_cancelled', 'Appointment Cancelled'),
                    ('appointment_completed', 'Appointment Completed'),
                    ('appointment_scheduled', 'New Appointment Scheduled'),
                    ('certificate_requested', 'Certificate Request Submitted'),
                    ('certificate_approved', 'Certificate Request Approved'),
                    ('certificate_ready', 'Certificate Ready for Collection'),
                    ('certificate_rejected', 'Certificate Request Rejected'),
                    ('certificate_processing', 'Certificate Being Processed'),
                    ('health_tip_new', 'New Health Tip Available'),
                    ('health_tip_updated', 'Health Tip Updated'),
                    ('medical_record_created', 'Medical Record Created'),
                    ('medical_record_updated', 'Medical Record Updated'),
                    ('health_form_incomplete', 'Health Form Incomplete'),
                    ('health_form_submitted', 'Health Form Submitted for Review'),
                    ('health_form_completed', 'Health Form Completed'),
                    ('patient_chart_submitted', 'Patient Chart Submitted'),
                    ('system_maintenance', 'System Maintenance'),
                    ('general_announcement', 'General Announcement'),
                    ('feedback_request', 'Feedback Request'),
                    ('direct_message', 'Direct Message'),
                    ('announcement_posted', 'Announcement Posted'),
                ],
                help_text='Specific transaction type for better routing',
                max_length=30,
                null=True,
            ),
        ),
        migrations.RunPython(forwards_backfill, backwards_noop),
    ]
