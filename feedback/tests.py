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
	email = email or f'{role}@feedback.test'
	return User.objects.create_user(email=email, password='test1234', role=role)


@override_settings(MIDDLEWARE=STRIPPED_MIDDLEWARE)
class FeedbackRoleAccessTests(TestCase):
	def setUp(self):
		self.student = _make_user(role='student', email='student@feedback.test')
		self.staff = _make_user(role='staff', email='staff@feedback.test')
		self.doctor = _make_user(role='doctor', email='doctor@feedback.test')
		self.admin_role = _make_user(role='admin', email='admin@feedback.test')

	def test_admin_role_cannot_access_feedback_list(self):
		self.client.force_login(self.admin_role)
		response = self.client.get(reverse('feedback:feedback_list'))
		self.assertEqual(response.status_code, 403)

	def test_admin_role_cannot_access_feedback_stats(self):
		self.client.force_login(self.admin_role)
		response = self.client.get(reverse('feedback:feedback_stats'))
		self.assertEqual(response.status_code, 403)

	def test_staff_can_access_feedback_stats(self):
		self.client.force_login(self.staff)
		response = self.client.get(reverse('feedback:feedback_stats'))
		self.assertEqual(response.status_code, 200)

	def test_doctor_can_access_feedback_stats(self):
		self.client.force_login(self.doctor)
		response = self.client.get(reverse('feedback:feedback_stats'))
		self.assertEqual(response.status_code, 200)

	def test_student_can_access_feedback_list(self):
		self.client.force_login(self.student)
		response = self.client.get(reverse('feedback:feedback_list'))
		self.assertEqual(response.status_code, 200)
