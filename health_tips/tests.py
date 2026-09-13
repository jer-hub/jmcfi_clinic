from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.template import Context, Template

from health_tips.templatetags.markdown_extras import markdown_format


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

	def test_upload_rejects_non_image_payload(self):
		self.client.force_login(self.staff)
		fake = SimpleUploadedFile('evil.png', b'not-an-image', content_type='image/png')
		response = self.client.post(
			reverse('health_tips:upload_image'),
			{'image': fake},
		)
		self.assertEqual(response.status_code, 400)


class MarkdownSanitizeTests(SimpleTestCase):
	def test_strips_script_tags(self):
		html = markdown_format('Hello <script>alert(1)</script>')
		self.assertNotIn('<script', str(html).lower())
		self.assertIn('Hello', str(html))

	def test_strips_onclick_handlers(self):
		html = markdown_format('<a href="https://example.com" onclick="alert(1)">x</a>')
		self.assertNotIn('onclick', str(html).lower())
		self.assertIn('href=', str(html))

	def test_template_filter_renders_safe_markdown(self):
		tpl = Template('{% load markdown_extras %}{{ body|markdown }}')
		out = tpl.render(Context({'body': '**bold**'}))
		self.assertIn('<strong>', out)
		self.assertIn('bold', out)
