from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0012_userinvite'),
    ]

    operations = [
        migrations.CreateModel(
            name='AccountProvisioningAudit',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action', models.CharField(choices=[('created_pending', 'Created (Pending Activation)'), ('created_active', 'Created (Active)'), ('activated', 'Activated'), ('suspended', 'Suspended')], max_length=30)),
                ('ip_address', models.CharField(blank=True, default='', max_length=45)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('actor', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='provisioning_actions', to='core.user')),
                ('target_user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='provisioning_audits', to='core.user')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
