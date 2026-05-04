from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse

from core.models import StaffProfile, User


def _complete_staff_like_profile(user, staff_id, department='Clinic Operations'):
	profile, _ = StaffProfile.objects.get_or_create(user=user)
	profile.staff_id = staff_id
	profile.department = department
	profile.phone = '09123456789'
	profile.save()
	return profile


@override_settings(
	MIDDLEWARE=[
		middleware
		for middleware in settings.MIDDLEWARE
		if middleware != 'core.middleware.ProfileCompleteMiddleware'
	]
)
class HealthFormsAdminAccessTests(TestCase):
	def setUp(self):
		self.admin_user = User.objects.create_user(
			email='admin-health@test.com',
			password='AdminPass123!',
			role='admin',
			is_staff=True,
			is_active=True,
		)
		self.admin_user.first_name = 'Admin'
		self.admin_user.last_name = 'User'
		self.admin_user.save(update_fields=['first_name', 'last_name'])
		_complete_staff_like_profile(self.admin_user, 'ADM-HF-001')
		self.client.force_login(self.admin_user)

	def test_admin_is_redirected_from_health_forms_list(self):
		response = self.client.get(reverse('health_forms_services:forms_list'))
		self.assertRedirects(response, reverse('core:dashboard'))
