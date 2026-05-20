from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('document_request', '0012_documentrequest_appointment'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='documentrequest',
            name='uniq_pending_document_request_per_type',
        ),
        migrations.RemoveConstraint(
            model_name='documentrequest',
            name='uniq_pending_document_request_per_appointment',
        ),
    ]
