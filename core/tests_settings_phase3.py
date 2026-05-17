from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from core.models import ClinicSettings, RoleSettings, UserPreferences
from core.settings_service import get_google_allowed_domains, invalidate_settings_cache
from core.utils import get_missing_profile_fields, is_profile_complete

User = get_user_model()

MIDDLEWARE_WITH_MAINTENANCE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'core.middleware.MaintenanceModeMiddleware',
]


@override_settings(MIDDLEWARE=MIDDLEWARE_WITH_MAINTENANCE)
class MaintenanceModeMiddlewareTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.patient = User.objects.create_user(
            email='patient-maint@test.com',
            password='pw',
            role='patient',
        )
        self.admin = User.objects.create_user(
            email='admin-maint@test.com',
            password='pw',
            role='admin',
        )
        clinic = ClinicSettings.load()
        clinic.maintenance_mode = True
        clinic.maintenance_message = 'Scheduled downtime'
        clinic.save()
        invalidate_settings_cache()

    def test_patient_sees_maintenance_page(self):
        self.client.force_login(self.patient)
        response = self.client.get(reverse('core:dashboard'))
        self.assertEqual(response.status_code, 503)
        self.assertIn(b'Scheduled downtime', response.content)

    def test_admin_can_access_during_maintenance(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('core:settings_hub'))
        self.assertEqual(response.status_code, 200)


class ProfileRequiredFieldsFromRoleSettingsTests(TestCase):
    def test_custom_required_fields_enforced(self):
        user = User.objects.create_user(
            email='staff-fields@test.com',
            password='pw',
            role='staff',
            first_name='A',
            last_name='B',
        )
        from core.models import StaffProfile

        profile, _ = StaffProfile.objects.get_or_create(
            user=user,
            defaults={
                'staff_id': 'S001',
                'department': 'Clinic',
                'phone': '+639171234567',
            },
        )
        profile.staff_id = 'S001'
        profile.department = 'Clinic'
        profile.phone = '+639171234567'
        profile.save()

        role = RoleSettings.objects.get(role='staff')
        role.profile_required_fields = ['first_name', 'last_name', 'staff_id', 'position']
        role.save()
        invalidate_settings_cache(role='staff')

        self.assertFalse(is_profile_complete(user))
        self.assertIn('position', [f[0] for f in get_missing_profile_fields(user)])


class GoogleDomainsFromClinicSettingsTests(TestCase):
    def test_clinic_domains_override_env_when_set(self):
        clinic = ClinicSettings.load()
        clinic.google_allowed_domains = 'clinic.test'
        clinic.save()
        invalidate_settings_cache()
        self.assertEqual(get_google_allowed_domains(), ['clinic.test'])


@override_settings(MIDDLEWARE=[
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
])
class ProfilePreferencesViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            email='prefs@test.com',
            password='pw',
            role='patient',
        )
        self.client.force_login(self.user)

    def test_preferences_page_loads(self):
        response = self.client.get(reverse('core:profile_preferences'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Preferences')

    def test_preferences_post_saves(self):
        prefs = UserPreferences.objects.get(user=self.user)
        response = self.client.post(
            reverse('core:profile_preferences'),
            {
                'email_notifications': '',
                'in_app_notifications': 'on',
                'compact_nav': 'on',
            },
        )
        self.assertRedirects(response, reverse('core:profile_preferences'))
        prefs.refresh_from_db()
        self.assertFalse(prefs.email_notifications)
        self.assertTrue(prefs.in_app_notifications)
        self.assertTrue(prefs.compact_nav)
