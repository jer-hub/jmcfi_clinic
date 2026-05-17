from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.models import Notification, RoleSettings, SettingsChangeLog, UserPreferences
from core.settings_service import invalidate_settings_cache
from core.utils import create_notification, create_bulk_notifications

User = get_user_model()

FEATURE_MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'core.middleware.RoleFeatureAccessMiddleware',
]


@override_settings(MIDDLEWARE=FEATURE_MIDDLEWARE)
class RoleFeatureAccessMiddlewareTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.patient = User.objects.create_user(
            email='patient-feature@test.com',
            password='pw',
            role='patient',
        )
        role = RoleSettings.objects.get(role='patient')
        role.can_access_analytics = False
        role.save()
        invalidate_settings_cache(role='patient')
        self.client.force_login(self.patient)

    def test_analytics_blocked_when_disabled(self):
        response = self.client.get(reverse('analytics:dashboard'))
        self.assertEqual(response.status_code, 302)

    def test_feedback_blocked_when_disabled(self):
        role = RoleSettings.objects.get(role='patient')
        role.can_submit_feedback = False
        role.save()
        invalidate_settings_cache(role='patient')
        response = self.client.get(reverse('feedback:feedback_list'))
        self.assertEqual(response.status_code, 302)


class NotificationPreferencesTests(TestCase):
    def test_create_notification_skipped_when_opted_out(self):
        user = User.objects.create_user(email='noprefs@test.com', password='pw', role='patient')
        prefs = UserPreferences.objects.get(user=user)
        prefs.in_app_notifications = False
        prefs.save()
        result = create_notification(user, 'T', 'M', notification_type='general')
        self.assertIsNone(result)
        self.assertEqual(Notification.objects.filter(user=user).count(), 0)

    def test_bulk_notifications_filters_opted_out(self):
        user_on = User.objects.create_user(email='on@test.com', password='pw', role='student')
        user_off = User.objects.create_user(email='off@test.com', password='pw', role='student')
        UserPreferences.objects.filter(user=user_off).update(in_app_notifications=False)
        created = create_bulk_notifications(
            [user_on, user_off],
            'Bulk',
            'Message',
            notification_type='general',
        )
        self.assertEqual(len(created), 1)
        self.assertEqual(Notification.objects.filter(user=user_on).count(), 1)
        self.assertEqual(Notification.objects.filter(user=user_off).count(), 0)


@override_settings(MIDDLEWARE=[
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
])
class SettingsAuditLogTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            email='admin-audit@test.com',
            password='pw',
            role='admin',
        )
        self.client.force_login(self.admin)

    def test_clinic_save_creates_audit_entries(self):
        url = reverse('core:settings_clinic')
        self.client.post(
            url,
            {
                'clinic_name': 'Audit Clinic',
                'support_email': '',
                'support_phone': '',
                'timezone': 'Asia/Manila',
                'date_format': 'Y-m-d',
                'google_allowed_domains': '',
                'default_session_hours': 24,
                'appointment_interval_minutes': 30,
                'max_advance_booking_days': 30,
                'cancellation_cutoff_hours': 24,
                'digest_hour': 8,
            },
        )
        self.assertTrue(
            SettingsChangeLog.objects.filter(
                setting_type=SettingsChangeLog.SettingType.CLINIC,
                field_name='clinic_name',
            ).exists()
        )

    def test_audit_page_renders(self):
        SettingsChangeLog.objects.create(
            setting_type=SettingsChangeLog.SettingType.ROLE,
            role='patient',
            field_name='can_access_analytics',
            old_value='True',
            new_value='False',
            changed_by=self.admin,
        )
        response = self.client.get(reverse('core:settings_audit'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'can_access_analytics')
