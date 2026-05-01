import hashlib
import re

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .adapters import GoogleOnlyAdapter
from .models import Notification, StaffProfile, StudentProfile, UserInvite
from .models import AccountProvisioningAudit

User = get_user_model()


def _complete_staff_like_profile(user, staff_id):
	user.first_name = user.first_name or 'Test'
	user.last_name = user.last_name or 'User'
	user.save(update_fields=['first_name', 'last_name'])

	profile, _ = StaffProfile.objects.get_or_create(user=user)
	profile.staff_id = staff_id
	profile.department = 'Clinic Operations'
	profile.phone = '09123456789'
	profile.save(update_fields=['staff_id', 'department', 'phone'])
	profile.refresh_from_db()

	# Clear stale relation caches so user.staff_profile reloads persisted values.
	user.__dict__.pop('staff_profile', None)
	user._state.fields_cache.pop('staff_profile', None)


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


class AdminLoginViewTests(TestCase):
	def setUp(self):
		cache.clear()
		self.url = reverse('core:admin_login')
		self.dashboard_url = reverse('core:dashboard')
		self.admin_user = User.objects.create_user(
			email='admin@jmcfi.edu.ph',
			password='AdminPass123!',
			role='admin',
			is_staff=True,
			is_active=True,
		)
		_complete_staff_like_profile(self.admin_user, 'ADM-LOGIN-001')
		self.student_user = User.objects.create_user(
			email='student@jmcfi.edu.ph',
			password='StudentPass123!',
			role='student',
			is_active=True,
		)

	def test_get_admin_login_page(self):
		response = self.client.get(self.url)
		self.assertEqual(response.status_code, 200)
		self.assertTemplateUsed(response, 'core/admin_login.html')

	def test_admin_login_inaccessible_for_authenticated_user(self):
		self.client.force_login(self.student_user)
		response = self.client.get(self.url)
		self.assertEqual(response.status_code, 302)
		self.assertNotEqual(response.url, self.url)

	def test_allows_admin_password_login(self):
		response = self.client.post(
			self.url,
			{
				'email': self.admin_user.email,
				'password': 'AdminPass123!',
				'remember_me': 'on',
			},
		)
		self.assertRedirects(response, self.dashboard_url)
		self.assertEqual(int(self.client.session.get('_auth_user_id')), self.admin_user.id)

	def test_rejects_non_admin_credentials(self):
		response = self.client.post(
			self.url,
			{
				'email': self.student_user.email,
				'password': 'StudentPass123!',
			},
		)
		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Invalid admin credentials.')
		self.assertNotIn('_auth_user_id', self.client.session)

	def test_blocks_after_too_many_failed_attempts(self):
		for _ in range(5):
			self.client.post(
				self.url,
				{
					'email': self.admin_user.email,
					'password': 'wrong-password',
				},
			)

		response = self.client.post(
			self.url,
			{
				'email': self.admin_user.email,
				'password': 'AdminPass123!',
			},
		)
		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Too many failed attempts. Try again in 15 minutes.')
		self.assertNotIn('_auth_user_id', self.client.session)

	def test_rejects_external_next_redirect(self):
		response = self.client.post(
			f"{self.url}?next=https://evil.example/phish",
			{
				'email': self.admin_user.email,
				'password': 'AdminPass123!',
				'next': 'https://evil.example/phish',
			},
		)
		self.assertRedirects(response, self.dashboard_url)

	def test_uses_browser_session_when_remember_me_unchecked(self):
		self.client.post(
			self.url,
			{
				'email': self.admin_user.email,
				'password': 'AdminPass123!',
			},
		)
		self.assertEqual(self.client.session.get_expire_at_browser_close(), True)


class LogoutViewTests(TestCase):
	def setUp(self):
		self.url = reverse('core:logout')
		self.login_url = reverse('account_login')
		self.user = User.objects.create_user(
			email='logout-user@jmcfi.edu.ph',
			password='LogoutPass123!',
			role='student',
			is_active=True,
		)

	def test_logout_accessible_when_already_logged_out(self):
		response = self.client.get(self.url)
		self.assertRedirects(response, self.login_url)

	def test_logout_redirects_authenticated_user_to_login(self):
		self.client.force_login(self.user)
		response = self.client.get(self.url)
		self.assertRedirects(response, self.login_url)
		self.assertNotIn('_auth_user_id', self.client.session)


class AccountLoginAccessControlTests(TestCase):
	def setUp(self):
		self.user = User.objects.create_user(
			email='login-access-user@jmcfi.edu.ph',
			password='LoginAccess123!',
			role='student',
			is_active=True,
		)

	def test_account_login_inaccessible_for_authenticated_user(self):
		self.client.force_login(self.user)
		response = self.client.get(reverse('account_login'))
		self.assertEqual(response.status_code, 302)
		self.assertNotEqual(response.url, reverse('account_login'))


class AdminDashboardNavigationTests(TestCase):
	def setUp(self):
		self.admin_user = User.objects.create_user(
			email='admin-nav@jmcfi.edu.ph',
			password='AdminNav123!',
			role='admin',
			is_active=True,
		)
		_complete_staff_like_profile(self.admin_user, 'ADM-NAV-001')

	def test_admin_dashboard_hides_removed_app_links(self):
		self.client.force_login(self.admin_user)
		response = self.client.get(reverse('core:dashboard'))

		self.assertEqual(response.status_code, 200)
		self.assertNotContains(response, f'href="{reverse("appointments:appointment_list")}"')
		self.assertNotContains(response, f'href="{reverse("medical_records:medical_records")}"')
		self.assertNotContains(response, f'href="{reverse("dental_records:dental_record_list")}"')
		self.assertNotContains(response, f'href="{reverse("document_request:document_requests")}"')
		self.assertNotContains(response, f'href="{reverse("health_forms_services:forms_list")}"')
		self.assertNotContains(response, f'href="{reverse("health_tips:health_tips_list")}"')
		self.assertNotContains(response, f'href="{reverse("pharmacy:dashboard")}"')
		self.assertNotContains(response, f'href="{reverse("feedback:feedback_list")}"')

	def test_admin_dashboard_keeps_expected_links_visible(self):
		self.client.force_login(self.admin_user)
		response = self.client.get(reverse('core:dashboard'))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, f'href="{reverse("core:user_management")}"')
		self.assertContains(response, f'href="{reverse("analytics:dashboard")}"')
		self.assertContains(response, f'href="{reverse("appointments:appointment_type_settings")}"')


class AdminRoleDirectAccessRestrictionTests(TestCase):
	def setUp(self):
		self.admin_user = User.objects.create_user(
			email='admin-direct-access@jmcfi.edu.ph',
			password='AdminDirect123!',
			role='admin',
			is_active=True,
		)
		_complete_staff_like_profile(self.admin_user, 'ADM-DIRECT-001')

	def test_admin_direct_access_is_blocked_for_removed_module_views(self):
		self.client.force_login(self.admin_user)

		blocked_urls = [
			reverse('appointments:appointment_list'),
			reverse('medical_records:medical_records'),
			reverse('dental_records:dental_record_list'),
			reverse('document_request:document_requests'),
		]

		for url in blocked_urls:
			with self.subTest(url=url):
				response = self.client.get(url)
				self.assertEqual(response.status_code, 403)

	def test_admin_direct_access_is_allowed_for_appointment_settings(self):
		self.client.force_login(self.admin_user)
		response = self.client.get(reverse('appointments:appointment_type_settings'))

		self.assertEqual(response.status_code, 200)


class StaffDashboardNavigationTests(TestCase):
	def setUp(self):
		self.staff_user = User.objects.create_user(
			email='staff-nav@jmcfi.edu.ph',
			password='StaffNav123!',
			role='staff',
			is_active=True,
		)
		_complete_staff_like_profile(self.staff_user, 'STF-NAV-001')

	def test_staff_dashboard_hides_document_request_links(self):
		self.client.force_login(self.staff_user)
		session = self.client.session
		session[f'profile_complete_{self.staff_user.id}_{self.staff_user.role}'] = True
		session.save()
		response = self.client.get(reverse('core:dashboard'))

		self.assertEqual(response.status_code, 200)
		self.assertNotContains(response, f'href="{reverse("document_request:document_requests")}"')

	def test_staff_dashboard_keeps_allowed_service_links_visible(self):
		self.client.force_login(self.staff_user)
		session = self.client.session
		session[f'profile_complete_{self.staff_user.id}_{self.staff_user.role}'] = True
		session.save()
		response = self.client.get(reverse('core:dashboard'))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, f'href="{reverse("appointments:appointment_list")}"')
		self.assertContains(response, f'href="{reverse("appointments:schedule_for_student")}"')
		self.assertContains(response, f'href="{reverse("medical_records:medical_records")}"')
		self.assertContains(response, f'href="{reverse("dental_records:dental_record_list")}"')


class AdminProfileCompletionRequirementTests(TestCase):
	def setUp(self):
		self.admin_user = User.objects.create_user(
			email='admin-profile-required@jmcfi.edu.ph',
			password='AdminProfile123!',
			role='admin',
			is_active=True,
		)

	def test_incomplete_admin_profile_redirects_to_profile_required(self):
		self.client.force_login(self.admin_user)
		response = self.client.get(reverse('core:dashboard'))

		self.assertRedirects(response, reverse('core:profile_required'))

	def test_incomplete_admin_can_access_edit_profile(self):
		self.client.force_login(self.admin_user)
		response = self.client.get(reverse('core:edit_profile'))

		self.assertEqual(response.status_code, 200)

	def test_incomplete_admin_cannot_bypass_with_session_cache(self):
		self.client.force_login(self.admin_user)
		session = self.client.session
		session[f'profile_complete_{self.admin_user.id}_{self.admin_user.role}'] = True
		session.save()

		response = self.client.get(reverse('core:dashboard'))
		self.assertRedirects(response, reverse('core:profile_required'))

	def test_incomplete_admin_is_redirected_from_other_protected_pages(self):
		self.client.force_login(self.admin_user)
		protected_urls = [
			reverse('core:dashboard'),
			reverse('core:profile'),
			reverse('core:notifications'),
			reverse('core:user_management'),
			reverse('appointments:appointment_type_settings'),
			reverse('appointments:appointment_list'),
			reverse('medical_records:medical_records'),
		]

		for url in protected_urls:
			with self.subTest(url=url):
				response = self.client.get(url)
				self.assertRedirects(response, reverse('core:profile_required'))

	def test_completed_admin_profile_allows_dashboard_access(self):
		_complete_staff_like_profile(self.admin_user, 'ADM-PROFILE-001')
		self.admin_user.first_name = 'Admin'
		self.admin_user.last_name = 'User'
		self.admin_user.save(update_fields=['first_name', 'last_name'])
		self.client.force_login(self.admin_user)
		response = self.client.get(reverse('core:dashboard'))

		self.assertEqual(response.status_code, 200)

	def test_admin_missing_first_name_is_blocked_from_dashboard(self):
		_complete_staff_like_profile(self.admin_user, 'ADM-PROFILE-002')
		self.admin_user.first_name = ''
		self.admin_user.last_name = 'User'
		self.admin_user.save(update_fields=['first_name', 'last_name'])
		self.client.force_login(self.admin_user)
		response = self.client.get(reverse('core:dashboard'))

		self.assertRedirects(response, reverse('core:profile_required'))

	def test_admin_missing_last_name_is_blocked_from_dashboard(self):
		_complete_staff_like_profile(self.admin_user, 'ADM-PROFILE-003')
		self.admin_user.first_name = 'Admin'
		self.admin_user.last_name = ''
		self.admin_user.save(update_fields=['first_name', 'last_name'])
		self.client.force_login(self.admin_user)
		response = self.client.get(reverse('core:dashboard'))

		self.assertRedirects(response, reverse('core:profile_required'))

	def test_admin_profile_page_hides_medical_and_professional_tabs(self):
		_complete_staff_like_profile(self.admin_user, 'ADM-PROFILE-004')
		self.admin_user.first_name = 'Admin'
		self.admin_user.last_name = 'User'
		self.admin_user.save(update_fields=['first_name', 'last_name'])
		self.client.force_login(self.admin_user)

		response = self.client.get(reverse('core:profile'))

		self.assertEqual(response.status_code, 200)
		self.assertNotContains(response, "activeTab = 'medical'")
		self.assertNotContains(response, "activeTab === 'professional'")

	def test_admin_edit_profile_hides_professional_and_medical_fields(self):
		_complete_staff_like_profile(self.admin_user, 'ADM-PROFILE-005')
		self.admin_user.first_name = 'Admin'
		self.admin_user.last_name = 'User'
		self.admin_user.save(update_fields=['first_name', 'last_name'])
		self.client.force_login(self.admin_user)

		response = self.client.get(reverse('core:edit_profile'))

		self.assertEqual(response.status_code, 200)
		self.assertNotContains(response, 'name="department"')
		self.assertNotContains(response, 'name="position"')
		self.assertNotContains(response, 'name="specialization"')
		self.assertNotContains(response, 'name="blood_type"')
		self.assertNotContains(response, 'name="allergies"')
		self.assertNotContains(response, 'name="medical_conditions"')

	def test_admin_quick_edit_rejects_medical_and_professional_fields(self):
		_complete_staff_like_profile(self.admin_user, 'ADM-PROFILE-006')
		profile = self.admin_user.staff_profile
		self.admin_user.first_name = 'Admin'
		self.admin_user.last_name = 'User'
		self.admin_user.save(update_fields=['first_name', 'last_name'])
		profile.position = 'Operations Lead'
		profile.allergies = 'Dust'
		profile.save(update_fields=['position', 'allergies'])
		self.client.force_login(self.admin_user)

		for field_name, attempted_value in [('position', 'Changed Position'), ('allergies', 'Pollen')]:
			with self.subTest(field_name=field_name):
				response = self.client.post(
					reverse('core:quick_edit_profile'),
					{'field_name': field_name, 'field_value': attempted_value},
				)
				self.assertRedirects(response, reverse('core:profile'))

		profile.refresh_from_db()
		self.assertEqual(profile.position, 'Operations Lead')
		self.assertEqual(profile.allergies, 'Dust')


@override_settings(
	AUTH_PASSWORD_VALIDATORS=[
		{'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
	]
)
class AdminUserCreateFlowTests(TestCase):
	def setUp(self):
		self.admin_user = User.objects.create_user(
			email='admin-create@jmcfi.edu.ph',
			password='AdminCreate123!',
			role='admin',
			is_staff=True,
			is_active=True,
		)
		_complete_staff_like_profile(self.admin_user, 'ADM-CREATE-001')
		self.client.force_login(self.admin_user)
		self.url = reverse('core:user_create')

	def _payload(self, **overrides):
		data = {
			'username': '',
			'email': 'new.student@jmcfi.edu.ph',
			'first_name': 'New',
			'last_name': 'Student',
			'role': 'student',
			'password1': 'ComplexPass123!',
			'password2': 'ComplexPass123!',
		}
		data.update(overrides)
		return data

	def test_create_user_allows_blank_username_and_creates_profile_and_notification(self):
		response = self.client.post(self.url, self._payload())

		created_user = User.objects.get(email='new.student@jmcfi.edu.ph')
		self.assertRedirects(response, reverse('core:user_detail', kwargs={'user_id': created_user.id}))
		self.assertIsNone(created_user.username)
		self.assertFalse(created_user.is_active)
		self.assertEqual(created_user.onboarding_status, User.ONBOARDING_STATUS.PENDING_ACTIVATION)
		self.assertTrue(StudentProfile.objects.filter(user=created_user).exists())
		self.assertTrue(
			Notification.objects.filter(
				user=created_user,
				title='Welcome to JMCFI Clinic',
				notification_type='general',
			).exists()
		)

	def test_create_user_normalizes_email_to_lowercase(self):
		self.client.post(self.url, self._payload(email='MixedCase.Student@JMCFI.EDU.PH'))

		self.assertTrue(User.objects.filter(email='mixedcase.student@jmcfi.edu.ph').exists())

	def test_create_user_activate_now_sets_active_lifecycle(self):
		self.client.post(
			self.url,
			self._payload(email='active.now@jmcfi.edu.ph', activate_now='on'),
		)

		created_user = User.objects.get(email='active.now@jmcfi.edu.ph')
		self.assertTrue(created_user.is_active)
		self.assertEqual(created_user.onboarding_status, User.ONBOARDING_STATUS.ACTIVE)

	def test_create_user_rejects_common_password(self):
		response = self.client.post(
			self.url,
			self._payload(password1='password123', password2='password123', email='weak.pass@jmcfi.edu.ph'),
		)

		self.assertEqual(response.status_code, 200)
		self.assertIn('password2', response.context['form'].errors)
		self.assertFalse(User.objects.filter(email='weak.pass@jmcfi.edu.ph').exists())

	def test_user_management_pending_filter_shows_only_pending_accounts(self):
		self.client.post(self.url, self._payload(email='pending.filter@jmcfi.edu.ph'))
		self.client.post(
			self.url,
			self._payload(email='active.filter@jmcfi.edu.ph', activate_now='on'),
		)

		response = self.client.get(reverse('core:user_management'), {'status': 'pending'})
		page_emails = {user.email for user in response.context['users'].object_list}

		self.assertEqual(response.status_code, 200)
		self.assertIn('pending.filter@jmcfi.edu.ph', page_emails)
		self.assertNotIn('active.filter@jmcfi.edu.ph', page_emails)


@override_settings(
	AUTH_PASSWORD_VALIDATORS=[
		{'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
	]
)
class AdminUserResetPasswordFlowTests(TestCase):
	def setUp(self):
		self.admin_user = User.objects.create_user(
			email='admin-reset@jmcfi.edu.ph',
			password='AdminReset123!',
			role='admin',
			is_staff=True,
			is_active=True,
		)
		_complete_staff_like_profile(self.admin_user, 'ADM-RESET-001')
		self.target_user = User.objects.create_user(
			email='target.reset@jmcfi.edu.ph',
			password='OldTargetPass123!',
			role='student',
			is_active=True,
		)
		self.client.force_login(self.admin_user)
		self.url = reverse('core:user_reset_password', kwargs={'user_id': self.target_user.id})

	def test_reset_password_rejects_common_password(self):
		response = self.client.post(
			self.url,
			{
				'new_password1': 'password123',
				'new_password2': 'password123',
			},
		)

		self.assertEqual(response.status_code, 200)
		self.assertIn('new_password2', response.context['form'].errors)

		self.target_user.refresh_from_db()
		self.assertTrue(self.target_user.check_password('OldTargetPass123!'))

	def test_reset_password_success_updates_password_and_notifies_user(self):
		response = self.client.post(
			self.url,
			{
				'new_password1': 'NewTargetPass123!',
				'new_password2': 'NewTargetPass123!',
			},
		)

		self.assertRedirects(
			response,
			reverse('core:user_detail', kwargs={'user_id': self.target_user.id}),
		)

		self.target_user.refresh_from_db()
		self.assertTrue(self.target_user.check_password('NewTargetPass123!'))
		self.assertTrue(
			Notification.objects.filter(
				user=self.target_user,
				title='Password Reset',
				notification_type='general',
			).exists()
		)


class AdminUserInviteLifecycleTests(TestCase):
	def setUp(self):
		self.admin_user = User.objects.create_user(
			email='admin-invite@jmcfi.edu.ph',
			password='AdminInvite123!',
			role='admin',
			is_staff=True,
			is_active=True,
		)
		_complete_staff_like_profile(self.admin_user, 'ADM-INVITE-001')
		self.client.force_login(self.admin_user)
		self.create_url = reverse('core:user_create')

	def _create_payload(self, **overrides):
		data = {
			'username': '',
			'email': 'invite.user@jmcfi.edu.ph',
			'first_name': 'Invite',
			'last_name': 'User',
			'role': 'student',
			'password1': 'InvitePass123!',
			'password2': 'InvitePass123!',
		}
		data.update(overrides)
		return data

	def _extract_token_from_response(self, response):
		content = response.content.decode('utf-8')
		match = re.search(r'/auth/invite/accept/([^"\s<]+)', content)
		self.assertIsNotNone(match)
		return match.group(1).rstrip('/')

	def test_pending_create_generates_invite_and_accept_activates_user(self):
		response = self.client.post(self.create_url, self._create_payload(), follow=True)
		created_user = User.objects.get(email='invite.user@jmcfi.edu.ph')

		self.assertContains(response, 'Invite link:')
		token = self._extract_token_from_response(response)

		invite = UserInvite.objects.get(user=created_user)
		self.assertIsNone(invite.accepted_at)
		self.assertIsNone(invite.revoked_at)
		self.assertGreater(invite.expires_at, timezone.now())
		self.assertFalse(created_user.is_active)
		self.assertEqual(created_user.onboarding_status, User.ONBOARDING_STATUS.PENDING_ACTIVATION)

		self.client.logout()
		accept_url = reverse('core:accept_invite', kwargs={'token': token})
		accept_response = self.client.post(accept_url)
		self.assertRedirects(accept_response, reverse('account_login'))

		created_user.refresh_from_db()
		invite.refresh_from_db()
		self.assertTrue(created_user.is_active)
		self.assertEqual(created_user.onboarding_status, User.ONBOARDING_STATUS.ACTIVE)
		self.assertIsNotNone(invite.accepted_at)

	def test_expired_invite_does_not_activate_user(self):
		pending_user = User.objects.create_user(
			email='expired.invite@jmcfi.edu.ph',
			password='ExpiredPass123!',
			role='student',
			is_active=False,
			onboarding_status=User.ONBOARDING_STATUS.PENDING_ACTIVATION,
		)
		raw_token = 'expired-token-sample'
		UserInvite.objects.create(
			user=pending_user,
			created_by=self.admin_user,
			token_hash=hashlib.sha256(raw_token.encode('utf-8')).hexdigest(),
			expires_at=timezone.now() - timezone.timedelta(hours=1),
		)

		self.client.logout()
		response = self.client.get(reverse('core:accept_invite', kwargs={'token': raw_token}))
		self.assertContains(response, 'This invite has expired.')

		pending_user.refresh_from_db()
		self.assertFalse(pending_user.is_active)
		self.assertEqual(pending_user.onboarding_status, User.ONBOARDING_STATUS.PENDING_ACTIVATION)

	def test_resend_invite_revokes_previous_invite(self):
		response = self.client.post(self.create_url, self._create_payload(email='resend.invite@jmcfi.edu.ph'), follow=True)
		created_user = User.objects.get(email='resend.invite@jmcfi.edu.ph')
		first_token = self._extract_token_from_response(response)
		first_hash = hashlib.sha256(first_token.encode('utf-8')).hexdigest()

		resend_response = self.client.get(
			reverse('core:user_resend_invite', kwargs={'user_id': created_user.id}),
			follow=True,
		)
		self.assertContains(resend_response, 'New invite link generated')
		second_token = self._extract_token_from_response(resend_response)
		second_hash = hashlib.sha256(second_token.encode('utf-8')).hexdigest()

		self.assertNotEqual(first_hash, second_hash)
		first_invite = UserInvite.objects.get(token_hash=first_hash)
		second_invite = UserInvite.objects.get(token_hash=second_hash)
		self.assertIsNotNone(first_invite.revoked_at)
		self.assertIsNone(second_invite.revoked_at)


class AdminProvisioningAuditTrailTests(TestCase):
	def setUp(self):
		self.admin_user = User.objects.create_user(
			email='admin-audit@jmcfi.edu.ph',
			password='AdminAudit123!',
			role='admin',
			is_staff=True,
			is_active=True,
		)
		_complete_staff_like_profile(self.admin_user, 'ADM-AUDIT-001')
		self.client.force_login(self.admin_user)

	def test_create_pending_logs_created_pending_audit(self):
		response = self.client.post(
			reverse('core:user_create'),
			{
				'username': '',
				'email': 'audit.pending@jmcfi.edu.ph',
				'first_name': 'Audit',
				'last_name': 'Pending',
				'role': 'student',
				'password1': 'AuditPass123!',
				'password2': 'AuditPass123!',
			},
		)
		self.assertEqual(response.status_code, 302)

		target = User.objects.get(email='audit.pending@jmcfi.edu.ph')
		audit = AccountProvisioningAudit.objects.get(target_user=target)
		self.assertEqual(audit.actor, self.admin_user)
		self.assertEqual(audit.action, AccountProvisioningAudit.ACTION.CREATED_PENDING)

	def test_create_active_logs_created_active_audit(self):
		response = self.client.post(
			reverse('core:user_create'),
			{
				'username': '',
				'email': 'audit.active@jmcfi.edu.ph',
				'first_name': 'Audit',
				'last_name': 'Active',
				'role': 'student',
				'password1': 'AuditPass123!',
				'password2': 'AuditPass123!',
				'activate_now': 'on',
			},
		)
		self.assertEqual(response.status_code, 302)

		target = User.objects.get(email='audit.active@jmcfi.edu.ph')
		audit = AccountProvisioningAudit.objects.get(target_user=target)
		self.assertEqual(audit.actor, self.admin_user)
		self.assertEqual(audit.action, AccountProvisioningAudit.ACTION.CREATED_ACTIVE)

	def test_toggle_logs_activate_and_suspend_audits(self):
		target = User.objects.create_user(
			email='audit.toggle@jmcfi.edu.ph',
			password='TogglePass123!',
			role='student',
			is_active=False,
			onboarding_status=User.ONBOARDING_STATUS.PENDING_ACTIVATION,
		)

		self.client.post(reverse('core:user_toggle_status', kwargs={'user_id': target.id}))
		self.client.post(reverse('core:user_toggle_status', kwargs={'user_id': target.id}))

		audits = list(
			AccountProvisioningAudit.objects.filter(target_user=target).order_by('created_at')
		)
		self.assertEqual(len(audits), 2)
		self.assertEqual(audits[0].actor, self.admin_user)
		self.assertEqual(audits[0].action, AccountProvisioningAudit.ACTION.ACTIVATED)
		self.assertEqual(audits[1].actor, self.admin_user)
		self.assertEqual(audits[1].action, AccountProvisioningAudit.ACTION.SUSPENDED)
