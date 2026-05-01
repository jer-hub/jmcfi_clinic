from django.test import TestCase, override_settings
from django.urls import reverse


STRIPPED_MIDDLEWARE = [
	'django.middleware.security.SecurityMiddleware',
	'django.contrib.sessions.middleware.SessionMiddleware',
	'django.middleware.common.CommonMiddleware',
	'django.middleware.csrf.CsrfViewMiddleware',
	'django.contrib.auth.middleware.AuthenticationMiddleware',
	'django.contrib.messages.middleware.MessageMiddleware',
	'django.middleware.clickjacking.XFrameOptionsMiddleware',
	'allauth.account.middleware.AccountMiddleware',
	'core.middleware.SessionTimeoutMiddleware',
	'core.middleware.RoleMiddleware',
]


def _make_user(role='student', email=None):
	from django.contrib.auth import get_user_model
	User = get_user_model()
	email = email or f'{role}@healthtips.test'
	return User.objects.create_user(email=email, password='test1234', role=role)


@override_settings(MIDDLEWARE=STRIPPED_MIDDLEWARE)
class HealthTipsRoleAccessTests(TestCase):
	def setUp(self):
		self.staff = _make_user(role='staff', email='staff@healthtips.test')
		self.admin_role = _make_user(role='admin', email='admin@healthtips.test')

	def test_staff_can_access_create_page(self):
		self.client.force_login(self.staff)
		response = self.client.get(reverse('health_tips:create_health_tip'))
		self.assertEqual(response.status_code, 200)

	def test_admin_role_cannot_access_create_page(self):
		self.client.force_login(self.admin_role)
		response = self.client.get(reverse('health_tips:create_health_tip'))
		self.assertEqual(response.status_code, 403)

	def test_admin_role_cannot_upload_tip_image(self):
		self.client.force_login(self.admin_role)
		response = self.client.post(reverse('health_tips:upload_image'))
		self.assertEqual(response.status_code, 403)
