from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from appointments.models import Appointment, AppointmentTypeDefault
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

    def test_academic_change_appears_on_audit_page(self):
        SettingsChangeLog.objects.create(
            setting_type=SettingsChangeLog.SettingType.ACADEMIC,
            field_name='college: Sample · name',
            old_value='Old Name',
            new_value='New Name',
            changed_by=self.admin,
        )
        response = self.client.get(reverse('core:settings_audit'))
        self.assertContains(response, 'Academic')
        self.assertContains(response, 'college: Sample')

    def test_appointment_doctor_assignment_creates_audit_entry(self):
        doctor = User.objects.create_user(
            email='audit-doctor@test.com',
            password='pw',
            role='doctor',
            first_name='Audit',
            last_name='Doctor',
        )
        type_key = Appointment.APPOINTMENT_TYPE_CHOICES[0][0]
        url = reverse('appointments:edit_appointment_type_default', kwargs={'type_key': type_key})
        response = self.client.post(
            url,
            {
                'appointment_type': type_key,
                'assigned_doctors': [str(doctor.pk)],
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            SettingsChangeLog.objects.filter(
                setting_type=SettingsChangeLog.SettingType.APPOINTMENT,
                field_name__contains='assigned_doctors',
            ).exists()
        )

    def test_appointment_doctor_assignment_htmx_creates_audit_entry(self):
        doctor = User.objects.create_user(
            email='audit-doctor-htmx@test.com',
            password='pw',
            role='doctor',
            first_name='Htmx',
            last_name='Doctor',
        )
        type_key = Appointment.APPOINTMENT_TYPE_CHOICES[0][0]
        url = reverse('appointments:edit_appointment_type_default', kwargs={'type_key': type_key})
        response = self.client.post(
            url,
            {
                'appointment_type': type_key,
                'assigned_doctors': [str(doctor.pk)],
            },
            HTTP_HX_REQUEST='true',
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            SettingsChangeLog.objects.filter(
                setting_type=SettingsChangeLog.SettingType.APPOINTMENT,
                field_name__contains='assigned_doctors',
            ).exists()
        )

    def test_appointment_doctor_assignment_skips_audit_when_unchanged(self):
        doctor = User.objects.create_user(
            email='audit-doctor-same@test.com',
            password='pw',
            role='doctor',
            first_name='Same',
            last_name='Doctor',
        )
        type_key = Appointment.APPOINTMENT_TYPE_CHOICES[0][0]
        default = AppointmentTypeDefault.objects.get(appointment_type=type_key)
        default.assigned_doctors.set([doctor])
        url = reverse('appointments:edit_appointment_type_default', kwargs={'type_key': type_key})
        before = SettingsChangeLog.objects.filter(setting_type=SettingsChangeLog.SettingType.APPOINTMENT).count()
        response = self.client.post(
            url,
            {
                'appointment_type': type_key,
                'assigned_doctors': [str(doctor.pk)],
            },
        )
        self.assertEqual(response.status_code, 302)
        after = SettingsChangeLog.objects.filter(setting_type=SettingsChangeLog.SettingType.APPOINTMENT).count()
        self.assertEqual(before, after)

    def test_appointment_toggle_creates_audit_entry(self):
        default = AppointmentTypeDefault.objects.first()
        self.assertIsNotNone(default)
        old_active = default.is_active
        url = reverse(
            'appointments:toggle_appointment_type_default',
            kwargs={'default_id': default.pk},
        )
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        log = SettingsChangeLog.objects.filter(
            setting_type=SettingsChangeLog.SettingType.APPOINTMENT,
            field_name__contains='is_active',
        ).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.old_value, 'True' if old_active else 'False')
        self.assertEqual(log.new_value, 'False' if old_active else 'True')

    def test_audit_page_filters_by_type(self):
        SettingsChangeLog.objects.create(
            setting_type=SettingsChangeLog.SettingType.ROLE,
            role='patient',
            field_name='role-field',
            old_value='a',
            new_value='b',
            changed_by=self.admin,
        )
        SettingsChangeLog.objects.create(
            setting_type=SettingsChangeLog.SettingType.ACADEMIC,
            field_name='academic-field',
            old_value='x',
            new_value='y',
            changed_by=self.admin,
        )
        response = self.client.get(reverse('core:settings_audit'), {'type': 'academic'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'academic-field')
        self.assertNotContains(response, 'role-field')

    def test_audit_page_has_live_filter_form(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('core:settings_audit'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'settings-audit-filter-form')
        self.assertContains(response, 'settings-audit-results')
        self.assertContains(response, 'Results update as you type')
        self.assertNotContains(response, '>Filter</button>')

    def test_audit_htmx_returns_results_partial(self):
        self.client.force_login(self.admin)
        response = self.client.get(
            reverse('core:settings_audit'),
            {'type': 'clinic'},
            HTTP_HX_REQUEST='true',
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'core/settings/audit_log/_results.html')
        self.assertNotContains(response, 'settings-audit-filter-form')

    def test_audit_csv_export_respects_filters(self):
        SettingsChangeLog.objects.create(
            setting_type=SettingsChangeLog.SettingType.CLINIC,
            field_name='clinic-visible',
            old_value='1',
            new_value='2',
            changed_by=self.admin,
        )
        SettingsChangeLog.objects.create(
            setting_type=SettingsChangeLog.SettingType.ROLE,
            field_name='role-hidden',
            old_value='1',
            new_value='2',
            changed_by=self.admin,
        )
        response = self.client.get(
            reverse('core:settings_audit'),
            {'type': 'clinic', 'export': 'csv'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')
        content = response.content.decode('utf-8')
        self.assertIn('clinic-visible', content)
        self.assertNotIn('role-hidden', content)
