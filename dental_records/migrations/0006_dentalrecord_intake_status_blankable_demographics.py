# Generated manually for guest dental intake drafts

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dental_records', '0005_dentalrecord_course_year_level'),
    ]

    operations = [
        migrations.AddField(
            model_name='dentalrecord',
            name='intake_status',
            field=models.CharField(
                blank=True,
                choices=[
                    ('', 'Not applicable'),
                    ('awaiting_guest', 'Awaiting guest'),
                    ('guest_submitted', 'Guest submitted'),
                ],
                default='',
                max_length=32,
            ),
        ),
        migrations.AlterField(
            model_name='dentalrecord',
            name='address',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AlterField(
            model_name='dentalrecord',
            name='civil_status',
            field=models.CharField(
                blank=True,
                choices=[
                    ('single', 'Single'),
                    ('married', 'Married'),
                    ('widowed', 'Widowed'),
                    ('separated', 'Separated'),
                    ('divorced', 'Divorced'),
                ],
                default='',
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name='dentalrecord',
            name='contact_number',
            field=models.CharField(blank=True, default='', max_length=20),
        ),
        migrations.AlterField(
            model_name='dentalrecord',
            name='date_of_birth',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='dentalrecord',
            name='department_college_office',
            field=models.CharField(blank=True, default='', max_length=200),
        ),
        migrations.AlterField(
            model_name='dentalrecord',
            name='designation',
            field=models.CharField(
                blank=True,
                choices=[('student', 'Student'), ('employee', 'Employee')],
                default='',
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name='dentalrecord',
            name='email',
            field=models.EmailField(blank=True, default='', max_length=254),
        ),
        migrations.AlterField(
            model_name='dentalrecord',
            name='gender',
            field=models.CharField(
                blank=True,
                choices=[('male', 'Male'), ('female', 'Female'), ('other', 'Other')],
                default='',
                max_length=10,
            ),
        ),
        migrations.AlterField(
            model_name='dentalrecord',
            name='guardian_contact',
            field=models.CharField(blank=True, default='', max_length=20),
        ),
        migrations.AlterField(
            model_name='dentalrecord',
            name='guardian_name',
            field=models.CharField(blank=True, default='', max_length=200),
        ),
        migrations.AlterField(
            model_name='dentalrecord',
            name='place_of_birth',
            field=models.CharField(blank=True, default='', max_length=200),
        ),
    ]
