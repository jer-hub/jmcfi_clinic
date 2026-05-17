from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings

from core.models import ClinicSettings, RoleSettings
from core.settings_service import (
    CLINIC_SETTINGS_CACHE_KEY,
    ROLE_SETTINGS_CACHE_KEY,
    get_appointment_interval_minutes,
    get_clinic_settings,
    get_effective_session_timeout,
    get_role_settings,
    invalidate_settings_cache,
)

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
class ClinicSettingsSingletonTests(TestCase):
    def test_load_creates_singleton(self):
        clinic = ClinicSettings.load()
        self.assertEqual(clinic.pk, ClinicSettings.SINGLETON_PK)
        self.assertEqual(ClinicSettings.objects.count(), 1)

    def test_second_load_returns_same_row(self):
        first = ClinicSettings.load()
        first.clinic_name = 'Test Clinic'
        first.save()
        second = ClinicSettings.load()
        self.assertEqual(second.clinic_name, 'Test Clinic')

    def test_delete_raises(self):
        clinic = ClinicSettings.load()
        with self.assertRaises(RuntimeError):
            clinic.delete()


@override_settings(MIDDLEWARE=STRIPPED_MIDDLEWARE)
class SettingsServiceCacheTests(TestCase):
    def setUp(self):
        cache.clear()
        invalidate_settings_cache()

    def test_clinic_settings_cached(self):
        clinic = get_clinic_settings()
        self.assertIsNotNone(cache.get(CLINIC_SETTINGS_CACHE_KEY))
        clinic.clinic_name = 'Cached Name'
        clinic.save()
        invalidate_settings_cache()
        refreshed = get_clinic_settings()
        self.assertEqual(refreshed.clinic_name, 'Cached Name')

    def test_role_settings_seeded_by_migration(self):
        self.assertEqual(RoleSettings.objects.count(), 4)
        admin = get_role_settings('admin')
        self.assertEqual(admin.session_timeout_seconds, 43200)
        patient = get_role_settings('patient')
        self.assertTrue(patient.can_book_appointments)

    def test_appointment_interval_from_clinic_settings(self):
        clinic = get_clinic_settings()
        clinic.appointment_interval_minutes = 45
        clinic.save()
        invalidate_settings_cache()
        self.assertEqual(get_appointment_interval_minutes(), 45)


@override_settings(MIDDLEWARE=STRIPPED_MIDDLEWARE)
class SessionTimeoutServiceTests(TestCase):
    def test_admin_session_timeout(self):
        user = User.objects.create_user(
            email='admin-settings@test.com',
            password='x',
            role='admin',
        )
        self.assertEqual(get_effective_session_timeout(user), 43200)

    def test_patient_session_timeout(self):
        user = User.objects.create_user(
            email='patient-settings@test.com',
            password='x',
            role='patient',
        )
        self.assertEqual(get_effective_session_timeout(user), 86400)

    def test_role_override_applies(self):
        user = User.objects.create_user(
            email='staff-settings@test.com',
            password='x',
            role='staff',
        )
        role = get_role_settings('staff')
        role.session_timeout_seconds = 3600
        role.save()
        invalidate_settings_cache(role='staff')
        self.assertEqual(get_effective_session_timeout(user), 3600)


@override_settings(MIDDLEWARE=STRIPPED_MIDDLEWARE)
class ClinicSettingsContextProcessorTests(TestCase):
    def test_context_processor_exposes_clinic_name(self):
        from django.test import RequestFactory

        from core.context_processors import clinic_settings_context

        clinic = get_clinic_settings()
        clinic.clinic_name = 'Context Clinic'
        clinic.save()
        invalidate_settings_cache()

        request = RequestFactory().get('/')
        ctx = clinic_settings_context(request)
        self.assertEqual(ctx['clinic_name'], 'Context Clinic')
        self.assertFalse(ctx['maintenance_mode'])
