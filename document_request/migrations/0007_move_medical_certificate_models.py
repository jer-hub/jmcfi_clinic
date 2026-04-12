from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('document_request', '0006_remove_documentrequest_scheduled_for_date_and_more'),
        ('health_forms_services', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.CreateModel(
                    name='DoctorSignature',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('signature_image', models.ImageField(upload_to='signatures/doctors/')),
                        ('is_active', models.BooleanField(default=True)),
                        ('created_at', models.DateTimeField(auto_now_add=True)),
                        ('updated_at', models.DateTimeField(auto_now=True)),
                        ('doctor', models.OneToOneField(limit_choices_to={'role': 'doctor'}, on_delete=django.db.models.deletion.CASCADE, related_name='doctor_signature', to=settings.AUTH_USER_MODEL)),
                        ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='updated_doctor_signatures', to=settings.AUTH_USER_MODEL)),
                    ],
                    options={
                        'verbose_name': 'Doctor Signature',
                        'verbose_name_plural': 'Doctor Signatures',
                        'ordering': ['doctor__last_name', 'doctor__first_name'],
                        'db_table': 'health_forms_services_doctorsignature',
                    },
                ),
                migrations.CreateModel(
                    name='MedicalCertificate',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('status', models.CharField(choices=[('pending', 'Pending Review'), ('completed', 'Completed'), ('rejected', 'Rejected')], default='pending', max_length=20)),
                        ('created_at', models.DateTimeField(auto_now_add=True)),
                        ('updated_at', models.DateTimeField(auto_now=True)),
                        ('reviewed_at', models.DateTimeField(blank=True, null=True)),
                        ('review_notes', models.TextField(blank=True)),
                        ('certificate_date', models.DateField(blank=True, help_text='Date printed on certificate', null=True)),
                        ('patient_name', models.CharField(help_text='Complete Name', max_length=200)),
                        ('age', models.PositiveIntegerField(blank=True, null=True)),
                        ('gender', models.CharField(blank=True, choices=[('male', 'Male'), ('female', 'Female')], max_length=10)),
                        ('address', models.TextField(blank=True)),
                        ('consultation_date', models.DateField(blank=True, help_text='Date patient came in for consult', null=True)),
                        ('diagnosis', models.TextField(blank=True, help_text='Diagnosis / medical findings')),
                        ('remarks_recommendations', models.TextField(blank=True, help_text='Remarks and recommendations')),
                        ('physician_name', models.CharField(blank=True, max_length=200)),
                        ('license_no', models.CharField(blank=True, max_length=100)),
                        ('ptr_no', models.CharField(blank=True, max_length=100, verbose_name='PTR No.')),
                        ('signed_at', models.DateTimeField(blank=True, null=True)),
                        ('signature_snapshot', models.ImageField(blank=True, upload_to='signatures/certificate_snapshots/')),
                        ('signature_hash', models.CharField(blank=True, max_length=64)),
                        ('reviewed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reviewed_medical_certificates', to=settings.AUTH_USER_MODEL)),
                        ('signed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='signed_medical_certificates', to=settings.AUTH_USER_MODEL)),
                        ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='medical_certificates', to=settings.AUTH_USER_MODEL)),
                    ],
                    options={
                        'verbose_name': 'Medical Certificate',
                        'verbose_name_plural': 'Medical Certificates',
                        'ordering': ['-created_at'],
                        'db_table': 'health_forms_services_medicalcertificate',
                    },
                ),
                migrations.AlterField(
                    model_name='documentrequest',
                    name='medical_certificate',
                    field=models.ForeignKey(blank=True, help_text='Linked medical certificate from Health Services', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='document_requests', to='document_request.medicalcertificate'),
                ),
            ],
        ),
    ]
