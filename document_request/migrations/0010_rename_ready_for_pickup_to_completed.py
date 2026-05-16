from django.db import migrations, models


def forwards_rename_status(apps, schema_editor):
    DocumentRequest = apps.get_model('document_request', 'DocumentRequest')
    DocumentRequest.objects.filter(status='ready_for_pickup').update(status='completed')


def backwards_rename_status(apps, schema_editor):
    DocumentRequest = apps.get_model('document_request', 'DocumentRequest')
    DocumentRequest.objects.filter(status='completed').update(status='ready_for_pickup')


class Migration(migrations.Migration):

    dependencies = [
        ('document_request', '0009_alter_cliniciansignature_options_and_more'),
    ]

    operations = [
        migrations.RunPython(forwards_rename_status, backwards_rename_status),
        migrations.AlterField(
            model_name='documentrequest',
            name='status',
            field=models.CharField(
                choices=[
                    ('pending_review', 'Pending review'),
                    ('completed', 'Completed'),
                    ('rejected', 'Rejected'),
                ],
                default='pending_review',
                max_length=20,
            ),
        ),
    ]
