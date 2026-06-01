"""Tests for academic catalog admin settings and profile integration."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.models import CollegeDepartment, CourseProgram, YearLevelOption, StaffProfile
from core.tests import _complete_staff_like_profile

User = get_user_model()


def _login_complete_admin(client, email='academic-admin@jmcfi.edu.ph', staff_id='ADM-ACAD'):
    admin = User.objects.create_user(
        email=email,
        password='AdminPass123!',
        role='admin',
        is_active=True,
    )
    _complete_staff_like_profile(admin, staff_id)
    client.force_login(admin)
    return admin


class AcademicCatalogMigrationTests(TestCase):
    def test_ibed_colleges_have_course_optional_after_migration(self):
        ibed = CollegeDepartment.objects.filter(name__startswith='IBED -').first()
        if ibed is None:
            self.skipTest('No IBED seed colleges in test DB')
        self.assertTrue(
            CollegeDepartment.objects.filter(name__startswith='IBED -', course_optional=True).exists()
        )


class AcademicSettingsAccessTests(TestCase):
    def setUp(self):
        self.admin = _login_complete_admin(self.client, 'academic-admin@jmcfi.edu.ph', 'ADM-ACAD-1')

    def test_admin_can_access_academic_hub(self):
        response = self.client.get(reverse('core:settings_academic_hub'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Academic catalog')

    def test_non_admin_cannot_access_academic_hub(self):
        staff = User.objects.create_user(
            email='staff-academic@jmcfi.edu.ph',
            password='StaffPass123!',
            role='staff',
            is_active=True,
        )
        self.client.force_login(staff)
        response = self.client.get(reverse('core:settings_academic_hub'))
        self.assertEqual(response.status_code, 302)


class AcademicCatalogCrudTests(TestCase):
    def setUp(self):
        _login_complete_admin(self.client, 'catalog-admin@jmcfi.edu.ph', 'ADM-CAT-1')

    def test_create_college_course_and_year_level(self):
        response = self.client.post(
            reverse('core:settings_college_create'),
            {'name': 'Test College of Nursing', 'course_optional': '', 'is_active': 'on'},
        )
        self.assertRedirects(response, reverse('core:settings_colleges'))
        college = CollegeDepartment.objects.get(name='Test College of Nursing')
        self.assertTrue(college.is_active)
        self.assertFalse(college.course_optional)

        response = self.client.post(
            reverse('core:settings_college_courses', kwargs={'pk': college.pk}),
            {'name': 'BS Nursing', 'is_active': 'on'},
        )
        self.assertRedirects(response, reverse('core:settings_college_courses', kwargs={'pk': college.pk}))
        self.assertTrue(
            CourseProgram.objects.filter(college_department=college, name='BS Nursing', is_active=True).exists()
        )

        response = self.client.post(
            reverse('core:settings_college_year_levels', kwargs={'pk': college.pk}),
            {'name': 'Year 1', 'sort_order': '1', 'is_active': 'on'},
        )
        self.assertRedirects(response, reverse('core:settings_college_year_levels', kwargs={'pk': college.pk}))
        self.assertTrue(
            YearLevelOption.objects.filter(college_department=college, name='Year 1', is_active=True).exists()
        )

    def test_deactivate_college_without_active_children(self):
        college = CollegeDepartment.objects.create(name='Lonely College', is_active=True)
        response = self.client.post(
            reverse('core:settings_colleges'),
            {'toggle_id': str(college.pk)},
        )
        self.assertEqual(response.status_code, 302)
        college.refresh_from_db()
        self.assertFalse(college.is_active)

    def test_deactivate_college_with_active_children_requires_confirm(self):
        college = CollegeDepartment.objects.create(name='Busy College', is_active=True)
        course = CourseProgram.objects.create(
            college_department=college,
            name='Busy Course',
            is_active=True,
        )
        response = self.client.post(
            reverse('core:settings_colleges'),
            {'toggle_id': str(college.pk)},
        )
        self.assertEqual(response.status_code, 302)
        college.refresh_from_db()
        course.refresh_from_db()
        self.assertTrue(college.is_active)
        self.assertTrue(course.is_active)

    def test_deactivate_college_with_active_children_cascades_when_confirmed(self):
        college = CollegeDepartment.objects.create(name='Cascade College', is_active=True)
        course = CourseProgram.objects.create(
            college_department=college,
            name='Cascade Course',
            is_active=True,
        )
        response = self.client.post(
            reverse('core:settings_colleges'),
            {'toggle_id': str(college.pk), 'confirm_cascade': '1'},
        )
        self.assertEqual(response.status_code, 302)
        college.refresh_from_db()
        course.refresh_from_db()
        self.assertFalse(college.is_active)
        self.assertFalse(course.is_active)

    def test_duplicate_course_name_per_college_rejected(self):
        college = CollegeDepartment.objects.create(name='Dup Test College', is_active=True)
        CourseProgram.objects.create(college_department=college, name='BS IT', is_active=True)
        response = self.client.post(
            reverse('core:settings_college_courses', kwargs={'pk': college.pk}),
            {'name': 'BS IT', 'is_active': 'on'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'already exists')


class AcademicProfileIntegrationTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email='patient-academic@jmcfi.edu.ph',
            password='PatientPass123!',
            role='patient',
            is_active=True,
            first_name='Pat',
            last_name='Academic',
        )
        self.college = CollegeDepartment.objects.create(
            name='Integration Test College',
            course_optional=True,
            is_active=True,
        )
        self.course = CourseProgram.objects.create(
            college_department=self.college,
            name='Integration Course',
            is_active=True,
        )
        self.inactive_course = CourseProgram.objects.create(
            college_department=self.college,
            name='Hidden Course',
            is_active=False,
        )
        self.client.force_login(self.admin)

    def test_edit_profile_includes_active_course_not_inactive(self):
        response = self.client.get(reverse('core:edit_profile'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Integration Course')
        self.assertNotContains(response, 'Hidden Course')

    def test_course_optional_college_allows_empty_course_on_save(self):
        from core.models import PatientProfile

        PatientProfile.objects.get_or_create(
            user=self.admin,
            defaults={
                'patient_id': 'INT-001',
                'phone': '+639171234567',
                'emergency_contact': 'Contact',
                'emergency_phone': '+639171234568',
                'date_of_birth': '2000-01-01',
            },
        )
        response = self.client.post(
            reverse('core:edit_profile'),
            {
                'first_name': 'Pat',
                'last_name': 'Academic',
                'patient_id': 'INT-001',
                'middle_name': 'M',
                'gender': 'male',
                'civil_status': 'single',
                'date_of_birth': '2000-01-01',
                'place_of_birth': 'City',
                'age': '24',
                'address': 'Addr',
                'phone': '+639171234567',
                'emergency_contact': 'Contact',
                'emergency_phone': '+639171234568',
                'department': self.college.name,
                'course': '',
                'year_level': '',
                'blood_type': 'O+',
            },
        )
        self.assertRedirects(response, reverse('core:profile'))
