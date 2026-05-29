from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse

from core.models import StaffProfile, User


def _staff_profile(user, staff_id):
    profile, _ = StaffProfile.objects.get_or_create(user=user)
    profile.staff_id = staff_id
    profile.department = 'Clinic Operations'
    profile.phone = '09123456789'
    profile.save()
    return profile


@override_settings(
    MIDDLEWARE=[
        m for m in settings.MIDDLEWARE
        if m != 'core.middleware.ProfileCompleteMiddleware'
    ],
)
class AnalyticsExportTests(TestCase):
    def setUp(self):
        self.doctor = User.objects.create_user(
            email='doctor-export@test.com',
            password='pass',
            role='doctor',
            is_staff=True,
            is_active=True,
            first_name='Export',
            last_name='Doctor',
        )
        _staff_profile(self.doctor, 'DOC-EXP-001')

        self.admin = User.objects.create_user(
            email='admin-export@test.com',
            password='pass',
            role='admin',
            is_staff=True,
            is_active=True,
            first_name='Export',
            last_name='Admin',
        )
        _staff_profile(self.admin, 'ADM-EXP-001')

    def test_staff_dashboard_export_for_doctor(self):
        self.client.force_login(self.doctor)
        url = reverse('analytics:export_report')
        response = self.client.get(url, {
            'report': 'staff_dashboard',
            'date_from': '2026-01-01',
            'date_to': '2026-12-31',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')
        body = response.content.decode()
        self.assertIn('Staff Analytics Dashboard', body)
        self.assertIn('Unique patients', body)

    def test_admin_dashboard_export_forbidden_for_doctor(self):
        self.client.force_login(self.doctor)
        url = reverse('analytics:export_report')
        response = self.client.get(url, {
            'report': 'admin_dashboard',
            'date_from': '2026-01-01',
            'date_to': '2026-12-31',
        })
        self.assertEqual(response.status_code, 403)

    def test_staff_dashboard_page_includes_export_control(self):
        self.client.force_login(self.doctor)
        response = self.client.get(reverse('analytics:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Export')
        self.assertContains(response, 'staff_dashboard')

    def test_health_trends_page_includes_export_menu(self):
        self.client.force_login(self.doctor)
        response = self.client.get(reverse('analytics:health_trends'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'health_trends_summary')
        self.assertContains(response, 'health_trends_live')

    def test_health_trends_summary_export(self):
        self.client.force_login(self.doctor)
        response = self.client.get(reverse('analytics:export_report'), {
            'report': 'health_trends_summary',
            'date_from': '2026-01-01',
            'date_to': '2026-12-31',
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('Health Trends', response.content.decode())

    def test_resource_utilization_page_includes_export_menu(self):
        self.client.force_login(self.doctor)
        response = self.client.get(reverse('analytics:resource_utilization'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'resource_utilization_summary')
        self.assertContains(response, 'resource_utilization_staff')

    def test_resource_utilization_summary_export(self):
        self.client.force_login(self.doctor)
        response = self.client.get(reverse('analytics:export_report'), {
            'report': 'resource_utilization_summary',
            'date_from': '2026-01-01',
            'date_to': '2026-12-31',
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('Resource Utilization', response.content.decode())

    def test_population_health_page_includes_export_menu(self):
        self.client.force_login(self.doctor)
        response = self.client.get(reverse('analytics:population_health'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'population_summary')
        self.assertContains(response, 'population_period')

    def test_population_summary_export(self):
        self.client.force_login(self.doctor)
        response = self.client.get(reverse('analytics:export_report'), {
            'report': 'population_summary',
            'date_from': '2026-01-01',
            'date_to': '2026-12-31',
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('Population Health', response.content.decode())

    def test_academic_page_includes_export_menu(self):
        self.client.force_login(self.doctor)
        response = self.client.get(reverse('analytics:academic_correlation'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'academic_summary')
        self.assertContains(response, 'academic_visitors')

    def test_academic_summary_export(self):
        self.client.force_login(self.doctor)
        response = self.client.get(reverse('analytics:export_report'), {
            'report': 'academic_summary',
            'date_from': '2026-01-01',
            'date_to': '2026-12-31',
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('Academic Correlation', response.content.decode())
