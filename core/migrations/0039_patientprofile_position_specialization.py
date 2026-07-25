from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0038_staffprofile_course_year_level'),
    ]

    operations = [
        migrations.AddField(
            model_name='patientprofile',
            name='position',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
        migrations.AddField(
            model_name='patientprofile',
            name='specialization',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
    ]
