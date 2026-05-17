from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from core.models import ClinicSettings, RoleSettings
from core.settings_service import get_appointment_interval_minutes, invalidate_settings_cache

User = get_user_model()

STRIPPED_MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
]


@override_settings(MIDDLEWARE=STRIPPED_MIDDLEWARE)
class SettingsViewsAccessTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            email='admin-settings-views@test.com',
            password='pw',
            role='admin',
        )
        self.student = User.objects.create_user(
            email='student-settings-views@test.com',
            password='pw',
            role='student',
        )

    def test_hub_requires_admin(self):
        self.client.force_login(self.student)
        response = self.client.get(reverse('core:settings_hub'))
        self.assertEqual(response.status_code, 302)

    def test_hub_renders_for_admin(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('core:settings_hub'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'System Settings')
        self.assertContains(response, 'Clinic settings')

    def test_invalid_role_redirects(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('core:settings_role_edit', kwargs={'role': 'invalid'}))
        self.assertRedirects(response, reverse('core:settings_roles'))


@override_settings(MIDDLEWARE=STRIPPED_MIDDLEWARE)
class SettingsViewsFormTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            email='admin-settings-forms@test.com',
            password='pw',
            role='admin',
        )
        self.client.force_login(self.admin)
        invalidate_settings_cache()

    def test_clinic_settings_post_updates_db(self):
        url = reverse('core:settings_clinic')
        response = self.client.post(
            url,
            {
                'clinic_name': 'Updated Clinic',
                'support_email': '',
                'support_phone': '',
                'timezone': 'Asia/Manila',
                'date_format': 'Y-m-d',
                'google_allowed_domains': 'test.edu.ph',
                'allow_student_self_signup': 'on',
                'default_session_hours': 24,
                'appointment_interval_minutes': 45,
                'max_advance_booking_days': 14,
                'cancellation_cutoff_hours': 12,
                'digest_hour': 9,
            },
        )
        self.assertRedirects(response, url)
        clinic = ClinicSettings.load()
        self.assertEqual(clinic.clinic_name, 'Updated Clinic')
        self.assertEqual(clinic.appointment_interval_minutes, 45)
        self.assertEqual(clinic.updated_by_id, self.admin.id)
        self.assertEqual(get_appointment_interval_minutes(), 45)

    def test_clinic_maintenance_requires_message(self):
        url = reverse('core:settings_clinic')
        response = self.client.post(
            url,
            {
                'clinic_name': 'Clinic',
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
                'maintenance_mode': 'on',
                'maintenance_message': '',
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'maintenance')

    def test_role_settings_post_updates_session(self):
        url = reverse('core:settings_role_edit', kwargs={'role': 'staff'})
        response = self.client.post(
            url,
            {
                'session_timeout_hours': 8,
                'profile_required_fields_text': 'first_name\nlast_name\nstaff_id',
                'can_access_analytics': 'on',
                'can_submit_feedback': 'on',
                'can_use_messaging': 'on',
            },
        )
        self.assertRedirects(response, url)
        role = RoleSettings.objects.get(role='staff')
        self.assertEqual(role.session_timeout_seconds, 8 * 3600)
        self.assertEqual(role.profile_required_fields, ['first_name', 'last_name', 'staff_id'])

    def test_roles_list_shows_all_roles(self):
        response = self.client.get(reverse('core:settings_roles'))
        self.assertEqual(response.status_code, 200)
        for label in ('Admin', 'Doctor', 'Staff', 'Student'):
            self.assertContains(response, label)
