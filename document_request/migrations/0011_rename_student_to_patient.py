# Generated manually for student → patient rename (Phase 1)

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def migrate_request_origin_forward(apps, schema_editor):
    DocumentRequest = apps.get_model('document_request', 'DocumentRequest')
    DocumentRequest.objects.filter(request_origin='student').update(request_origin='patient')


def migrate_request_origin_reverse(apps, schema_editor):
    DocumentRequest = apps.get_model('document_request', 'DocumentRequest')
    DocumentRequest.objects.filter(request_origin='patient').update(request_origin='student')


class Migration(migrations.Migration):

    dependencies = [
        ('document_request', '0010_rename_ready_for_pickup_to_completed'),
        ('core', '0019_rename_student_to_patient'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RunPython(migrate_request_origin_forward, migrate_request_origin_reverse),
        migrations.RemoveConstraint(
            model_name='documentrequest',
            name='uniq_pending_document_request_per_type',
        ),
        migrations.RenameField(
            model_name='documentrequest',
            old_name='student',
            new_name='patient',
        ),
        migrations.AlterField(
            model_name='documentrequest',
            name='patient',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='document_requests',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name='documentrequest',
            name='request_origin',
            field=models.CharField(
                choices=[('patient', 'Patient'), ('doctor', 'Doctor/Admin')],
                default='patient',
                max_length=20,
            ),
        ),
        migrations.AddConstraint(
            model_name='documentrequest',
            constraint=models.UniqueConstraint(
                condition=models.Q(('status', 'pending_review')),
                fields=('patient', 'document_type'),
                name='uniq_pending_document_request_per_type',
            ),
        ),
    ]
