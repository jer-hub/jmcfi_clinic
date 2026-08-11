# Generated manually for guest rename

from django.db import migrations


def forwards_walkin_to_guest_emails(apps, schema_editor):
    User = apps.get_model('core', 'User')
    for user in User.objects.filter(email__iendswith='@walkin.local').iterator():
        local, _, _domain = user.email.partition('@')
        if local.lower().startswith('walkin-'):
            local = 'guest-' + local[len('walkin-') :]
        user.email = f'{local}@guest.local'
        user.save(update_fields=['email'])


def backwards_guest_to_walkin_emails(apps, schema_editor):
    User = apps.get_model('core', 'User')
    for user in User.objects.filter(email__iendswith='@guest.local').iterator():
        local, _, _domain = user.email.partition('@')
        if local.lower().startswith('guest-'):
            local = 'walkin-' + local[len('guest-') :]
        user.email = f'{local}@walkin.local'
        user.save(update_fields=['email'])


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0046_patientprofile_contact_email_guest_access_token'),
    ]

    operations = [
        migrations.RunPython(forwards_walkin_to_guest_emails, backwards_guest_to_walkin_emails),
    ]
