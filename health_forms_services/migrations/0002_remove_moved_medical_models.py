from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('health_forms_services', '0001_initial'),
        ('document_request', '0007_move_medical_certificate_models'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.DeleteModel(name='DoctorSignature'),
                migrations.DeleteModel(name='MedicalCertificate'),
            ],
        ),
    ]
