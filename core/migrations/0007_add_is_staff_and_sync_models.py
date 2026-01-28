# Generated manually to add is_staff back and sync model state

from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0006_alter_user_email_alter_user_username'),
    ]

    operations = [
        # Add is_staff field back to User model
        migrations.AddField(
            model_name='user',
            name='is_staff',
            field=models.BooleanField(
                default=False,
                help_text='Designates whether the user can log into the admin site.',
            ),
        ),
        
        # These operations use state_operations to sync Django's model state
        # with the existing database tables (tables already exist from management app)
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name='Notification',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('title', models.CharField(max_length=200)),
                        ('message', models.TextField()),
                        ('notification_type', models.CharField(choices=[('appointment', 'Appointment Reminder'), ('certificate', 'Certificate Update'), ('health_tip', 'Health Tip'), ('general', 'General Notification')], max_length=20)),
                        ('transaction_type', models.CharField(blank=True, choices=[('appointment_reminder', 'Appointment Reminder'), ('appointment_confirmed', 'Appointment Confirmed'), ('appointment_cancelled', 'Appointment Cancelled'), ('appointment_completed', 'Appointment Completed'), ('appointment_scheduled', 'New Appointment Scheduled'), ('certificate_requested', 'Certificate Request Submitted'), ('certificate_approved', 'Certificate Request Approved'), ('certificate_ready', 'Certificate Ready for Collection'), ('certificate_rejected', 'Certificate Request Rejected'), ('certificate_processing', 'Certificate Being Processed'), ('health_tip_new', 'New Health Tip Available'), ('health_tip_updated', 'Health Tip Updated'), ('medical_record_created', 'Medical Record Created'), ('medical_record_updated', 'Medical Record Updated'), ('system_maintenance', 'System Maintenance'), ('general_announcement', 'General Announcement'), ('feedback_request', 'Feedback Request')], help_text='Specific transaction type for better routing', max_length=30, null=True)),
                        ('related_id', models.PositiveIntegerField(blank=True, help_text='ID of the related object (appointment, certificate request, etc.)', null=True)),
                        ('is_read', models.BooleanField(default=False)),
                        ('created_at', models.DateTimeField(auto_now_add=True)),
                        ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='notifications', to=settings.AUTH_USER_MODEL)),
                    ],
                    options={
                        'db_table': 'management_notification',
                        'ordering': ['-created_at'],
                    },
                ),
            ],
            database_operations=[],  # No database changes - table already exists
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name='StudentProfile',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('student_id', models.CharField(max_length=20, unique=True)),
                        ('profile_image', models.ImageField(blank=True, help_text='Profile photo', null=True, upload_to='profiles/students/')),
                        ('middle_name', models.CharField(blank=True, default='', max_length=100)),
                        ('gender', models.CharField(blank=True, choices=[('male', 'Male'), ('female', 'Female'), ('other', 'Other')], default='', max_length=10)),
                        ('civil_status', models.CharField(blank=True, choices=[('single', 'Single'), ('married', 'Married'), ('widowed', 'Widowed'), ('separated', 'Separated')], default='', max_length=20)),
                        ('date_of_birth', models.DateField(blank=True, null=True)),
                        ('place_of_birth', models.CharField(blank=True, default='', max_length=200)),
                        ('age', models.IntegerField(blank=True, null=True)),
                        ('address', models.TextField(blank=True, default='')),
                        ('phone', models.CharField(blank=True, default='', max_length=20)),
                        ('telephone_number', models.CharField(blank=True, default='', max_length=20)),
                        ('emergency_contact', models.CharField(blank=True, default='', max_length=100)),
                        ('emergency_phone', models.CharField(blank=True, default='', max_length=20)),
                        ('course', models.CharField(blank=True, default='', max_length=100)),
                        ('year_level', models.CharField(blank=True, choices=[('1', 'First Year'), ('2', 'Second Year'), ('3', 'Third Year'), ('4', 'Fourth Year'), ('5', 'Fifth Year'), ('graduate', 'Graduate')], default='', max_length=10)),
                        ('department', models.CharField(blank=True, default='', max_length=100)),
                        ('blood_type', models.CharField(blank=True, choices=[('A+', 'A+'), ('A-', 'A-'), ('B+', 'B+'), ('B-', 'B-'), ('AB+', 'AB+'), ('AB-', 'AB-'), ('O+', 'O+'), ('O-', 'O-')], max_length=5, null=True)),
                        ('allergies', models.TextField(blank=True, default='')),
                        ('medical_conditions', models.TextField(blank=True, default='')),
                        ('created_at', models.DateTimeField(auto_now_add=True)),
                        ('updated_at', models.DateTimeField(auto_now=True)),
                        ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='student_profile', to=settings.AUTH_USER_MODEL)),
                    ],
                    options={
                        'db_table': 'management_studentprofile',
                    },
                ),
            ],
            database_operations=[],  # No database changes - table already exists
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name='StaffProfile',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('staff_id', models.CharField(max_length=20, unique=True)),
                        ('profile_image', models.ImageField(blank=True, help_text='Profile photo', null=True, upload_to='profiles/staff/')),
                        ('middle_name', models.CharField(blank=True, default='', max_length=100)),
                        ('gender', models.CharField(blank=True, choices=[('male', 'Male'), ('female', 'Female'), ('other', 'Other')], default='', max_length=10)),
                        ('civil_status', models.CharField(blank=True, choices=[('single', 'Single'), ('married', 'Married'), ('widowed', 'Widowed'), ('separated', 'Separated')], default='', max_length=20)),
                        ('date_of_birth', models.DateField(blank=True, null=True)),
                        ('place_of_birth', models.CharField(blank=True, default='', max_length=200)),
                        ('age', models.IntegerField(blank=True, null=True)),
                        ('address', models.TextField(blank=True, default='')),
                        ('phone', models.CharField(blank=True, default='', max_length=20)),
                        ('telephone_number', models.CharField(blank=True, default='', max_length=20)),
                        ('emergency_contact', models.CharField(blank=True, default='', max_length=100)),
                        ('emergency_phone', models.CharField(blank=True, default='', max_length=20)),
                        ('department', models.CharField(blank=True, default='', max_length=100)),
                        ('position', models.CharField(blank=True, default='', max_length=100)),
                        ('specialization', models.CharField(blank=True, max_length=100)),
                        ('license_number', models.CharField(blank=True, max_length=50)),
                        ('blood_type', models.CharField(blank=True, choices=[('A+', 'A+'), ('A-', 'A-'), ('B+', 'B+'), ('B-', 'B-'), ('AB+', 'AB+'), ('AB-', 'AB-'), ('O+', 'O+'), ('O-', 'O-')], max_length=5, null=True)),
                        ('allergies', models.TextField(blank=True, default='')),
                        ('medical_conditions', models.TextField(blank=True, default='')),
                        ('created_at', models.DateTimeField(auto_now_add=True)),
                        ('updated_at', models.DateTimeField(auto_now=True)),
                        ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='staff_profile', to=settings.AUTH_USER_MODEL)),
                    ],
                    options={
                        'db_table': 'management_staffprofile',
                    },
                ),
            ],
            database_operations=[],  # No database changes - table already exists
        ),
    ]
