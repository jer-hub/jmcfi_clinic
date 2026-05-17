from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings

from core.models import ClinicSettings, Notification, UserPreferences
from core.notification_delivery import notify_user, send_notification_email
from core.settings_service import invalidate_settings_cache

User = get_user_model()


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class EmailNotificationDeliveryTests(TestCase):
    def setUp(self):
        mail.outbox.clear()
        self.user = User.objects.create_user(
            email='email-notify@test.com',
            password='pw',
            role='student',
        )
        clinic = ClinicSettings.load()
        clinic.enable_email_notifications = True
        clinic.save()
        invalidate_settings_cache()
        prefs = UserPreferences.objects.get(user=self.user)
        prefs.email_notifications = True
        prefs.in_app_notifications = True
        prefs.save()

    def test_notify_user_sends_email_when_enabled(self):
        notify_user(self.user, 'Test Subject', 'Test body message')
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Test Subject', mail.outbox[0].subject)
        self.assertEqual(mail.outbox[0].to, [self.user.email])

    def test_email_skipped_when_clinic_disabled(self):
        clinic = ClinicSettings.load()
        clinic.enable_email_notifications = False
        clinic.save()
        invalidate_settings_cache()
        self.assertFalse(send_notification_email(self.user, 'T', 'B'))
        self.assertEqual(len(mail.outbox), 0)

    def test_email_skipped_when_user_opted_out(self):
        prefs = UserPreferences.objects.get(user=self.user)
        prefs.email_notifications = False
        prefs.save()
        notify_user(self.user, 'T', 'Body')
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(Notification.objects.filter(user=self.user).count(), 1)
