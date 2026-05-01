from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0011_user_onboarding_status'),
    ]

    operations = [
        migrations.CreateModel(
            name='UserInvite',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('token_hash', models.CharField(db_index=True, max_length=64, unique=True)),
                ('expires_at', models.DateTimeField()),
                ('accepted_at', models.DateTimeField(blank=True, null=True)),
                ('revoked_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_user_invites', to='core.user')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='invites', to='core.user')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
