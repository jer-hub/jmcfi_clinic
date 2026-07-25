from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0037_middle_name_optional'),
    ]

    operations = [
        migrations.AddField(
            model_name='staffprofile',
            name='course',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
        migrations.AddField(
            model_name='staffprofile',
            name='year_level',
            field=models.CharField(blank=True, default='', max_length=20),
        ),
    ]
