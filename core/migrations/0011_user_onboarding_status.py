from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0010_add_shs_k12_specializations'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='onboarding_status',
            field=models.CharField(
                choices=[
                    ('pending_activation', 'Pending Activation'),
                    ('active', 'Active'),
                    ('suspended', 'Suspended'),
                ],
                default='active',
                max_length=20,
            ),
        ),
    ]
