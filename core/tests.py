from django.test import SimpleTestCase, override_settings

from .adapters import GoogleOnlyAdapter


class GoogleOnlyAdapterDomainPolicyTests(SimpleTestCase):
	def setUp(self):
		self.adapter = GoogleOnlyAdapter()

	@override_settings(GOOGLE_ALLOWED_DOMAINS=[])
	def test_allows_any_email_when_domain_list_empty(self):
		self.assertTrue(self.adapter._is_allowed_email('user@example.com'))

	@override_settings(GOOGLE_ALLOWED_DOMAINS=['jmc.edu.ph', 'jmcfi.edu.ph'])
	def test_allows_email_from_allowed_domain(self):
		self.assertTrue(self.adapter._is_allowed_email('user@jmc.edu.ph'))

	@override_settings(GOOGLE_ALLOWED_DOMAINS=['jmc.edu.ph'])
	def test_blocks_email_from_non_allowed_domain(self):
		self.assertFalse(self.adapter._is_allowed_email('user@gmail.com'))

	@override_settings(GOOGLE_ALLOWED_DOMAINS=['jmc.edu.ph'])
	def test_blocks_invalid_email_format(self):
		self.assertFalse(self.adapter._is_allowed_email('invalid-email'))
