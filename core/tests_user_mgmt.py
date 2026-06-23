"""
Comprehensive tests for user management improvements:
- Soft delete / restore
- Onboarding status synchronization
- Bulk operations
- Audit log
- Export CSV
- Stale user cleanup
- Last activity tracking
"""
import csv
import json
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import CommonPasswordValidator
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .forms import BulkUserActionForm, UserExportForm
from .models import (
    AccountProvisioningAudit,
    Notification,
    StaffProfile,
    StudentProfile,
    UserInvite,
)

User = get_user_model()


def _complete_staff_like_profile(user, staff_id):
    """Helper to complete a staff-like profile (staff/doctor/admin)."""
    user.first_name = user.first_name or 'Test'
    user.last_name = user.last_name or 'User'
    user.save(update_fields=['first_name', 'last_name'])

    profile, _ = StaffProfile.objects.get_or_create(user=user)
    profile.staff_id = staff_id
    profile.middle_name = 'M'
    profile.gender = 'male'
    profile.civil_status = 'single'
    profile.religion = 'Roman Catholic'
    profile.citizenship = 'Filipino'
    profile.date_of_birth = '2000-01-01'
    profile.place_of_birth = 'Davao'
    profile.age = 26
    profile.address = '123 Clinic St, Davao'
    profile.zip_code = '8000'
    profile.department = 'Clinic Operations'
    profile.phone = '+639123456789'
    profile.emergency_contact = 'Emergency Person'
    profile.emergency_phone = '+639123456780'
    profile.save(
        update_fields=[
            'staff_id',
            'middle_name',
            'gender',
            'civil_status',
            'religion',
            'citizenship',
            'date_of_birth',
            'place_of_birth',
            'age',
            'address',
            'zip_code',
            'department',
            'phone',
            'emergency_contact',
            'emergency_phone',
        ]
    )
    profile.refresh_from_db()

    user.__dict__.pop('staff_profile', None)
    user._state.fields_cache.pop('staff_profile', None)


def _complete_doctor_profile(user, staff_id):
    _complete_staff_like_profile(user, staff_id)
    profile = user.staff_profile
    profile.position = 'Attending Physician'
    profile.license_number = 'PRC-123456'
    profile.ptr_no = 'PTR-789012'
    profile.save(update_fields=['position', 'license_number', 'ptr_no'])
    profile.refresh_from_db()
    user.__dict__.pop('staff_profile', None)
    user._state.fields_cache.pop('staff_profile', None)


def _complete_student_profile(user, student_id):
    """Helper to complete a student profile."""
    user.first_name = user.first_name or 'Test'
    user.last_name = user.last_name or 'Student'
    user.save(update_fields=['first_name', 'last_name'])

    profile, _ = StudentProfile.objects.get_or_create(user=user)
    profile.patient_id = student_id
    profile.phone = '+639123456789'
    profile.emergency_contact = 'Emergency Contact'
    profile.emergency_phone = '+639987654321'
    profile.date_of_birth = '2000-01-01'
    profile.department = 'College of Science'
    profile.course = 'BS Computer Science'
    profile.year_level = '1st Year'
    profile.gender = 'male'
    profile.civil_status = 'single'
    profile.religion = 'Roman Catholic'
    profile.citizenship = 'Filipino'
    profile.place_of_birth = 'Manila'
    profile.age = 23
    profile.address = 'Manila'
    profile.zip_code = '1000'
    profile.blood_type = 'O+'
    profile.save()
    profile.refresh_from_db()

    user.__dict__.pop('patient_profile', None)
    user._state.fields_cache.pop('patient_profile', None)


# ============================================================================
# Model Tests
# ============================================================================

class UserModelSoftDeleteTests(TestCase):
    """Tests for the soft-delete and restore functionality."""

    def setUp(self):
        self.user = User.objects.create_user(
            email='softdelete@test.com',
            password='TestPass123!',
            role='patient',
            is_active=True,
        )

    def test_soft_delete_sets_flags(self):
        self.user.soft_delete()
        self.user.refresh_from_db()

        self.assertTrue(self.user.is_deleted)
        self.assertIsNotNone(self.user.deleted_at)
        self.assertFalse(self.user.is_active)
        self.assertEqual(self.user.onboarding_status, User.ONBOARDING_STATUS.SUSPENDED)

    def test_restore_reverses_soft_delete(self):
        self.user.soft_delete()
        self.user.restore()
        self.user.refresh_from_db()

        self.assertFalse(self.user.is_deleted)
        self.assertIsNone(self.user.deleted_at)
        self.assertTrue(self.user.is_active)
        self.assertEqual(self.user.onboarding_status, User.ONBOARDING_STATUS.ACTIVE)

    def test_soft_deleted_user_not_in_default_queryset(self):
        self.user.soft_delete()
        self.assertFalse(User.objects.filter(is_deleted=False, id=self.user.id).exists())

    def test_soft_deleted_user_still_in_database(self):
        self.user.soft_delete()
        self.assertTrue(User.objects.filter(id=self.user.id, is_deleted=True).exists())


class UserModelOnboardingSyncTests(TestCase):
    """Tests for onboarding_status/is_active synchronization."""

    def setUp(self):
        self.user = User.objects.create_user(
            email='sync-test@test.com',
            password='TestPass123!',
            role='patient',
        )

    def test_pending_activation_with_active_sets_active(self):
        self.user.onboarding_status = User.ONBOARDING_STATUS.PENDING_ACTIVATION
        self.user.is_active = True
        self.user.save()
        self.user.refresh_from_db()
        self.assertEqual(self.user.onboarding_status, User.ONBOARDING_STATUS.ACTIVE)

    def test_active_with_inactive_sets_suspended(self):
        self.user.is_active = False
        self.user.save()
        self.user.refresh_from_db()
        self.assertEqual(self.user.onboarding_status, User.ONBOARDING_STATUS.SUSPENDED)

    def test_suspended_with_active_sets_active(self):
        self.user.onboarding_status = User.ONBOARDING_STATUS.SUSPENDED
        self.user.is_active = True
        self.user.save()
        self.user.refresh_from_db()
        self.assertEqual(self.user.onboarding_status, User.ONBOARDING_STATUS.ACTIVE)

    def test_sync_onboarding_status_method(self):
        self.user.is_active = True
        self.user.onboarding_status = User.ONBOARDING_STATUS.PENDING_ACTIVATION
        self.user.sync_onboarding_status()
        self.assertEqual(self.user.onboarding_status, User.ONBOARDING_STATUS.ACTIVE)


# ============================================================================
# View Tests
# ============================================================================

class AdminBulkActionTests(TestCase):
    """Tests for bulk user operations."""

    def setUp(self):
        self.admin_user = User.objects.create_user(
            email='admin-bulk@test.com',
            password='AdminPass123!',
            role='admin',
            is_staff=True,
            is_active=True,
        )
        _complete_staff_like_profile(self.admin_user, 'ADM-BULK-001')

        self.target_users = []
        for i in range(5):
            user = User.objects.create_user(
                email=f'bulk-target-{i}@test.com',
                password='TestPass123!',
                role='patient',
                is_active=True,
            )
            self.target_users.append(user)

        self.client.force_login(self.admin_user)
        self.url = reverse('core:user_bulk_action')

    def test_bulk_activate(self):
        # First deactivate all
        User.objects.filter(id__in=[u.id for u in self.target_users]).update(
            is_active=False,
            onboarding_status='suspended',
        )
        user_ids = ','.join(str(u.id) for u in self.target_users)

        response = self.client.post(self.url, {
            'action': 'activate',
            'user_ids': user_ids,
            'confirmation': True,
        })

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'success')

        for user in self.target_users:
            user.refresh_from_db()
            self.assertTrue(user.is_active)
            self.assertEqual(user.onboarding_status, 'active')

    def test_bulk_deactivate(self):
        user_ids = ','.join(str(u.id) for u in self.target_users)

        response = self.client.post(self.url, {
            'action': 'deactivate',
            'user_ids': user_ids,
            'confirmation': True,
        })

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'success')

        for user in self.target_users:
            user.refresh_from_db()
            self.assertFalse(user.is_active)
            self.assertEqual(user.onboarding_status, 'suspended')

    def test_bulk_soft_delete(self):
        user_ids = ','.join(str(u.id) for u in self.target_users)

        response = self.client.post(self.url, {
            'action': 'delete',
            'user_ids': user_ids,
            'confirmation': True,
        })

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'success')

        for user in self.target_users:
            user.refresh_from_db()
            self.assertTrue(user.is_deleted)
            self.assertIsNotNone(user.deleted_at)

    def test_bulk_soft_delete_accepts_checkbox_user_ids(self):
        targets = self.target_users[:2]
        response = self.client.post(
            self.url,
            {
                'action': 'delete',
                'confirmation': 'True',
                'user_ids': [str(user.id) for user in targets],
            },
        )
        self.assertEqual(response.status_code, 200)
        for user in targets:
            user.refresh_from_db()
            self.assertTrue(user.is_deleted)

    def test_bulk_soft_delete_htmx_returns_table_partial(self):
        target = self.target_users[0]
        response = self.client.post(
            self.url,
            {
                'action': 'delete',
                'confirmation': 'True',
                'user_ids': [str(target.id)],
            },
            HTTP_HX_REQUEST='true',
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'hx-trigger')
        self.assertNotContains(response, target.email)
        target.refresh_from_db()
        self.assertTrue(target.is_deleted)

    def test_bulk_soft_delete_with_duplicate_user_id_list(self):
        """Simulates duplicate checkbox values from mobile + desktop rows."""
        target = self.target_users[0]
        response = self.client.post(
            self.url,
            {
                'action': 'delete',
                'confirmation': 'True',
                'user_ids': [str(target.id), str(target.id)],
            },
        )
        self.assertEqual(response.status_code, 200)
        target.refresh_from_db()
        self.assertTrue(target.is_deleted)

    def test_bulk_action_skips_admin_users(self):
        admin_user2 = User.objects.create_user(
            email='admin-bulk2@test.com',
            password='AdminPass123!',
            role='admin',
            is_active=True,
        )
        user_ids = ','.join(str(u.id) for u in [admin_user2, self.target_users[0]])

        response = self.client.post(self.url, {
            'action': 'deactivate',
            'user_ids': user_ids,
            'confirmation': True,
        })

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'success')

        admin_user2.refresh_from_db()
        self.assertTrue(admin_user2.is_active)  # Should not be deactivated

    def test_bulk_action_requires_post(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)

    def test_bulk_action_requires_valid_form(self):
        response = self.client.post(self.url, {
            'action': 'invalid',
            'user_ids': '1,2,3',
            'confirmation': True,
        })
        self.assertEqual(response.status_code, 400)

    def test_bulk_action_creates_audit_logs(self):
        user_ids = ','.join(str(u.id) for u in self.target_users[:2])

        self.client.post(self.url, {
            'action': 'deactivate',
            'user_ids': user_ids,
            'confirmation': True,
        })

        audits = AccountProvisioningAudit.objects.filter(
            action=AccountProvisioningAudit.ACTION.BULK_SUSPENDED,
        )
        self.assertEqual(audits.count(), 2)

    def test_bulk_action_creates_notifications(self):
        user_ids = ','.join(str(u.id) for u in self.target_users[:3])

        self.client.post(self.url, {
            'action': 'activate',
            'user_ids': user_ids,
            'confirmation': True,
        })

        notifications = Notification.objects.filter(
            title='Account Activated',
            user__in=self.target_users[:3],
        )
        self.assertEqual(notifications.count(), 3)


class AdminUserToggleStatusTests(TestCase):
    """Tests for HTMX status toggle feedback."""

    def setUp(self):
        self.admin_user = User.objects.create_user(
            email='admin-toggle@test.com',
            password='AdminPass123!',
            role='admin',
            is_staff=True,
            is_active=True,
        )
        _complete_staff_like_profile(self.admin_user, 'ADM-TOGGLE-001')

        self.target_user = User.objects.create_user(
            email='target-toggle@test.com',
            password='TestPass123!',
            role='patient',
            is_active=True,
        )
        self.client.force_login(self.admin_user)
        self.url = reverse('core:user_toggle_status', kwargs={'user_id': self.target_user.id})

    def test_toggle_status_htmx_emits_toast(self):
        response = self.client.post(self.url, HTTP_HX_REQUEST='true')

        self.assertEqual(response.status_code, 200)
        self.assertIn('HX-Trigger', response.headers)
        self.assertIn('updateStatus', response.headers['HX-Trigger'])
        self.assertIn('user-toast', response.headers['HX-Trigger'])

        self.target_user.refresh_from_db()
        self.assertFalse(self.target_user.is_active)
        self.assertEqual(self.target_user.onboarding_status, User.ONBOARDING_STATUS.SUSPENDED)


class AdminUserRestoreTests(TestCase):
    """Tests for restoring soft-deleted users."""

    def setUp(self):
        self.admin_user = User.objects.create_user(
            email='admin-restore@test.com',
            password='AdminPass123!',
            role='admin',
            is_staff=True,
            is_active=True,
        )
        _complete_staff_like_profile(self.admin_user, 'ADM-RESTORE-001')

        self.target_user = User.objects.create_user(
            email='target-restore@test.com',
            password='TestPass123!',
            role='patient',
            is_active=True,
        )
        self.target_user.soft_delete()

        self.client.force_login(self.admin_user)
        self.url = reverse('core:user_restore', kwargs={'user_id': self.target_user.id})

    def test_restore_restores_user(self):
        response = self.client.post(self.url)
        self.assertRedirects(response, reverse('core:deleted_user_management'))

        self.target_user.refresh_from_db()
        self.assertFalse(self.target_user.is_deleted)
        self.assertTrue(self.target_user.is_active)

    def test_restore_htmx_stays_on_deleted_page(self):
        response = self.client.post(self.url, HTTP_HX_REQUEST='true')
        self.assertEqual(response.status_code, 200)
        self.assertIn('HX-Trigger', response.headers)
        self.assertIn('user-toast', response.headers['HX-Trigger'])
        self.assertContains(response, 'Deleted Accounts')

        self.target_user.refresh_from_db()
        self.assertFalse(self.target_user.is_deleted)
        self.assertTrue(self.target_user.is_active)

    def test_restore_creates_notification(self):
        self.client.post(self.url)
        self.assertTrue(
            Notification.objects.filter(
                user=self.target_user,
                title='Account Restored',
            ).exists()
        )

    def test_restore_creates_audit_log(self):
        self.client.post(self.url)
        self.assertTrue(
            AccountProvisioningAudit.objects.filter(
                target_user=self.target_user,
                action=AccountProvisioningAudit.ACTION.RESTORED,
            ).exists()
        )


class AdminUserDeleteTests(TestCase):
    """Tests for soft-deleting users from the admin flow."""

    def setUp(self):
        self.admin_user = User.objects.create_user(
            email='admin-delete@test.com',
            password='AdminPass123!',
            role='admin',
            is_staff=True,
            is_active=True,
        )
        _complete_staff_like_profile(self.admin_user, 'ADM-DELETE-001')

        self.target_user = User.objects.create_user(
            email='target-delete@test.com',
            password='TestPass123!',
            role='patient',
            is_active=True,
        )
        self.client.force_login(self.admin_user)
        self.url = reverse('core:user_delete', kwargs={'user_id': self.target_user.id})

    def test_delete_soft_deletes_user(self):
        response = self.client.post(self.url)
        self.assertRedirects(response, reverse('core:user_management'))

        self.target_user.refresh_from_db()
        self.assertTrue(self.target_user.is_deleted)

    def test_delete_get_redirects_to_user_detail(self):
        response = self.client.get(self.url)
        self.assertRedirects(response, reverse('core:user_detail', kwargs={'user_id': self.target_user.id}))

    def test_delete_htmx_get_returns_modal_partial(self):
        response = self.client.get(self.url, HTTP_HX_REQUEST='true')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'core/user_management/_user_delete_modal.html')
        self.assertContains(response, 'Are you sure you want to soft-delete this user?')


class AdminDeletedUsersBulkActionTests(TestCase):
    """Tests for bulk actions on deleted users."""

    def setUp(self):
        self.admin_user = User.objects.create_user(
            email='admin-bulk-action@test.com',
            password='AdminPass123!',
            role='admin',
            is_staff=True,
            is_active=True,
        )
        _complete_staff_like_profile(self.admin_user, 'ADM-BULK-ACTION-001')

        self.restore_users = []
        for idx in range(2):
            user = User.objects.create_user(
                email=f'bulk-restore-{idx}@test.com',
                password='TestPass123!',
                role='patient',
                is_active=True,
            )
            user.soft_delete()
            self.restore_users.append(user)

        self.delete_users = []
        for idx in range(2):
            user = User.objects.create_user(
                email=f'bulk-delete-{idx}@test.com',
                password='TestPass123!',
                role='patient',
                is_active=True,
            )
            user.soft_delete()
            self.delete_users.append(user)

        self.client.force_login(self.admin_user)
        self.url = reverse('core:deleted_user_bulk_action')

    def test_bulk_restore_restores_multiple_users(self):
        response = self.client.post(
            self.url,
            {
                'bulk_action': 'restore',
                'user_ids': [str(user.id) for user in self.restore_users],
            },
            HTTP_HX_REQUEST='true',
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('HX-Trigger', response.headers)
        self.assertIn('user-toast', response.headers['HX-Trigger'])

        for user in self.restore_users:
            user.refresh_from_db()
            self.assertFalse(user.is_deleted)
            self.assertTrue(user.is_active)

    def test_bulk_delete_permanently_removes_multiple_users(self):
        user_ids = [str(user.id) for user in self.delete_users]
        response = self.client.post(
            self.url,
            {
                'bulk_action': 'delete_permanently',
                'user_ids': user_ids,
            },
            HTTP_HX_REQUEST='true',
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('HX-Trigger', response.headers)
        self.assertIn('user-toast', response.headers['HX-Trigger'])
        self.assertFalse(User.objects.filter(id__in=user_ids).exists())

    def test_bulk_action_requires_selection(self):
        response = self.client.post(self.url, {'bulk_action': 'restore'}, HTTP_HX_REQUEST='true')
        self.assertEqual(response.status_code, 200)
        self.assertIn('HX-Trigger', response.headers)
        self.assertIn('error', response.headers['HX-Trigger'])

    def test_deleted_list_bulk_apply_uses_confirmation_modal(self):
        response = self.client.get(reverse('core:deleted_user_management'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertContains(response, 'deleted-users-bulk-form')
        self.assertContains(response, 'deletedUsersBulkForm')
        self.assertContains(response, '@click="openBulkConfirm()"')
        self.assertContains(response, 'Restore selected users?')
        self.assertContains(response, 'Delete permanently?')
        self.assertContains(response, "getElementById('deleted-users-bulk-form')")
        self.assertContains(response, 'actionLabel: \'Restore\'')
        self.assertContains(response, 'actionLabel: \'Delete permanently\'')
        apply_idx = content.find('openBulkConfirm')
        self.assertGreater(apply_idx, -1)
        self.assertIn('type="button"', content[max(0, apply_idx - 250):apply_idx + 80])


class AdminDeletedUserPermanentDeleteTests(TestCase):
    """Tests for permanently deleting a single deleted user."""

    def setUp(self):
        self.admin_user = User.objects.create_user(
            email='admin-permanent-delete@test.com',
            password='AdminPass123!',
            role='admin',
            is_staff=True,
            is_active=True,
        )
        _complete_staff_like_profile(self.admin_user, 'ADM-PERM-DELETE-001')

        self.target_user = User.objects.create_user(
            email='target-permanent-delete@test.com',
            password='TestPass123!',
            role='patient',
            is_active=True,
        )
        self.target_user.soft_delete()

        self.client.force_login(self.admin_user)
        self.url = reverse('core:deleted_user_permanent_delete', kwargs={'user_id': self.target_user.id})

    def test_permanent_delete_removes_user(self):
        response = self.client.post(self.url)
        self.assertRedirects(response, reverse('core:deleted_user_management'))
        self.assertFalse(User.objects.filter(id=self.target_user.id).exists())

    def test_permanent_delete_htmx_stays_on_deleted_page(self):
        response = self.client.post(self.url, HTTP_HX_REQUEST='true')
        self.assertEqual(response.status_code, 200)
        self.assertIn('HX-Trigger', response.headers)
        self.assertIn('user-toast', response.headers['HX-Trigger'])
        self.assertContains(response, 'Deleted Accounts')
        self.assertFalse(User.objects.filter(id=self.target_user.id).exists())

    def test_deleted_list_row_actions_exclude_restore_and_permanent_delete(self):
        response = self.client.get(reverse('core:deleted_user_management'))
        self.assertEqual(response.status_code, 200)
        form_id = f'deleted-user-permanent-delete-form-{self.target_user.id}'
        self.assertNotContains(response, form_id)
        self.assertNotContains(response, reverse('core:user_restore', kwargs={'user_id': self.target_user.id}))
        self.assertContains(response, reverse('core:user_detail', kwargs={'user_id': self.target_user.id}))
        self.assertContains(response, reverse('core:user_audit_log', kwargs={'user_id': self.target_user.id}))


class AdminUserDetailTests(TestCase):
    """Tests for user detail behavior across roles."""

    def setUp(self):
        self.admin_user = User.objects.create_user(
            email='admin-detail@test.com',
            password='AdminPass123!',
            role='admin',
            is_staff=True,
            is_active=True,
        )
        _complete_staff_like_profile(self.admin_user, 'ADM-DETAIL-001')
        AccountProvisioningAudit.objects.create(
            actor=self.admin_user,
            target_user=self.admin_user,
            action=AccountProvisioningAudit.ACTION.ACTIVATED,
            ip_address='127.0.0.1',
        )
        self.client.force_login(self.admin_user)

    def test_admin_detail_shows_staff_profile_fields(self):
        response = self.client.get(reverse('core:user_detail', kwargs={'user_id': self.admin_user.id}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'ADM-DETAIL-001')
        self.assertContains(response, 'Recent Audit Log')

    def test_admin_detail_uses_breadcrumb_subnav(self):
        response = self.client.get(reverse('core:user_detail', kwargs={'user_id': self.admin_user.id}))
        self.assertContains(response, 'aria-label="Breadcrumb"')
        self.assertContains(response, 'Users')
        self.assertContains(response, reverse('core:user_management'))


class AdminUserEditProfileTests(TestCase):
    """Tests for admin edit user with full profile mirror."""

    def setUp(self):
        self.admin_user = User.objects.create_user(
            email='admin-profile-edit@test.com',
            password='AdminPass123!',
            role='admin',
            is_staff=True,
            is_active=True,
        )
        _complete_staff_like_profile(self.admin_user, 'ADM-PROF-EDIT')
        self.client.force_login(self.admin_user)

    def test_get_patient_edit_shows_academic_section(self):
        patient = User.objects.create_user(
            email='patient-profile-edit@test.com',
            password='PatientPass123!',
            role='patient',
            first_name='Pat',
            last_name='Ient',
            is_active=True,
        )
        _complete_student_profile(patient, 'PAT-PROF-001')

        response = self.client.get(
            reverse('core:user_edit', kwargs={'user_id': patient.id}),
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'core/user_management/user_edit.html')
        self.assertContains(response, 'Academic Information')
        self.assertContains(response, 'studentAcademicEditForm')

    def test_get_staff_edit_shows_staff_sections(self):
        staff = User.objects.create_user(
            email='staff-profile-edit@test.com',
            password='StaffPass123!',
            role='staff',
            first_name='St',
            last_name='Aff',
            is_active=True,
        )
        _complete_staff_like_profile(staff, 'STAFF-PROF-001')

        response = self.client.get(
            reverse('core:user_edit', kwargs={'user_id': staff.id}),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Staff ID')
        self.assertContains(response, 'Professional Information')
        self.assertContains(response, 'Contact Information')
        self.assertContains(response, 'name="position"')

    def test_get_doctor_edit_keeps_position_admin_editable(self):
        doctor = User.objects.create_user(
            email='doctor-profile-edit@test.com',
            password='DoctorPass123!',
            role='doctor',
            first_name='Doc',
            last_name='Tor',
            is_active=True,
        )
        _complete_doctor_profile(doctor, 'DOC-PROF-001')

        response = self.client.get(
            reverse('core:user_edit', kwargs={'user_id': doctor.id}),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Clinical Credentials')
        self.assertContains(response, 'name="position"')

    def test_post_updates_staff_profile_fields(self):
        staff = User.objects.create_user(
            email='staff-post-edit@test.com',
            password='StaffPass123!',
            role='staff',
            first_name='St',
            last_name='Aff',
            is_active=True,
        )
        _complete_staff_like_profile(staff, 'STAFF-OLD')
        profile = staff.staff_profile

        response = self.client.post(
            reverse('core:user_edit', kwargs={'user_id': staff.id}),
            {
                'email': staff.email,
                'first_name': staff.first_name,
                'last_name': staff.last_name,
                'role': 'staff',
                'is_active': 'on',
                'staff_id': 'STAFF-NEW',
                'middle_name': profile.middle_name,
                'gender': profile.gender,
                'civil_status': profile.civil_status,
                'religion': profile.religion,
                'citizenship': profile.citizenship,
                'date_of_birth': profile.date_of_birth,
                'place_of_birth': profile.place_of_birth,
                'age': profile.age,
                'address': '456 Updated Avenue, Davao',
                'zip_code': '8001',
                'phone': '+639171234567',
                'emergency_contact': profile.emergency_contact,
                'emergency_phone': profile.emergency_phone,
                'department': profile.department,
            },
        )
        self.assertRedirects(
            response,
            reverse('core:user_detail', kwargs={'user_id': staff.id}),
        )
        profile.refresh_from_db()
        self.assertEqual(profile.staff_id, 'STAFF-NEW')
        self.assertEqual(profile.phone, '+639171234567')
        self.assertEqual(profile.address, '456 Updated Avenue, Davao')

    def test_post_updates_doctor_position_for_admin(self):
        doctor = User.objects.create_user(
            email='doctor-post-edit@test.com',
            password='DoctorPass123!',
            role='doctor',
            first_name='Doc',
            last_name='Tor',
            is_active=True,
        )
        _complete_doctor_profile(doctor, 'DOC-OLD')
        profile = doctor.staff_profile

        response = self.client.post(
            reverse('core:user_edit', kwargs={'user_id': doctor.id}),
            {
                'email': doctor.email,
                'first_name': doctor.first_name,
                'last_name': doctor.last_name,
                'role': 'doctor',
                'is_active': 'on',
                'staff_id': profile.staff_id,
                'middle_name': profile.middle_name,
                'gender': profile.gender,
                'civil_status': profile.civil_status,
                'religion': profile.religion,
                'citizenship': profile.citizenship,
                'date_of_birth': profile.date_of_birth,
                'place_of_birth': profile.place_of_birth,
                'age': profile.age,
                'address': profile.address,
                'zip_code': profile.zip_code,
                'phone': profile.phone,
                'emergency_contact': profile.emergency_contact,
                'emergency_phone': profile.emergency_phone,
                'department': profile.department,
                'position': 'Dental Officer',
                'license_number': profile.license_number,
                'ptr_no': profile.ptr_no,
            },
        )
        self.assertRedirects(
            response,
            reverse('core:user_detail', kwargs={'user_id': doctor.id}),
        )
        profile.refresh_from_db()
        self.assertEqual(profile.position, 'Dental Officer')

    def test_post_role_change_recreates_profile_stub(self):
        staff = User.objects.create_user(
            email='role-change-staff@test.com',
            password='StaffPass123!',
            role='staff',
            first_name='Role',
            last_name='Change',
            is_active=True,
        )
        _complete_staff_like_profile(staff, 'STAFF-ROLE-OLD')
        profile = staff.staff_profile

        response = self.client.post(
            reverse('core:user_edit', kwargs={'user_id': staff.id}),
            {
                'email': staff.email,
                'first_name': staff.first_name,
                'last_name': staff.last_name,
                'role': 'patient',
                'is_active': 'on',
                'staff_id': 'SHOULD-NOT-APPLY',
                'middle_name': profile.middle_name,
                'gender': profile.gender,
                'civil_status': profile.civil_status,
                'religion': profile.religion,
                'citizenship': profile.citizenship,
                'date_of_birth': profile.date_of_birth,
                'place_of_birth': profile.place_of_birth,
                'age': profile.age,
                'address': profile.address,
                'zip_code': profile.zip_code,
                'phone': profile.phone,
                'emergency_contact': profile.emergency_contact,
                'emergency_phone': profile.emergency_phone,
                'department': profile.department,
            },
        )
        self.assertRedirects(
            response,
            reverse('core:user_edit', kwargs={'user_id': staff.id}),
        )
        staff.refresh_from_db()
        self.assertEqual(staff.role, 'patient')
        self.assertFalse(StaffProfile.objects.filter(user=staff).exists())
        patient_profile = StudentProfile.objects.get(user=staff)
        self.assertTrue(patient_profile.patient_id.startswith('TEMP_'))
        self.assertNotEqual(patient_profile.patient_id, 'SHOULD-NOT-APPLY')

    def test_admin_target_role_and_active_fields_locked(self):
        admin_target = User.objects.create_user(
            email='admin-target-edit@test.com',
            password='AdminPass123!',
            role='admin',
            first_name='Ad',
            last_name='Min',
            is_active=True,
        )
        _complete_staff_like_profile(admin_target, 'ADM-TARGET-001')

        response = self.client.get(
            reverse('core:user_edit', kwargs={'user_id': admin_target.id}),
        )
        self.assertEqual(response.status_code, 200)
        user_form = response.context['user_form']
        self.assertTrue(user_form.fields['role'].disabled)
        self.assertTrue(user_form.fields['is_active'].disabled)
        self.assertContains(response, 'disabled')


class AdminUserEditSubnavTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(
            email='admin-edit-nav@test.com',
            password='AdminPass123!',
            role='admin',
            is_staff=True,
            is_active=True,
        )
        _complete_staff_like_profile(self.admin_user, 'ADM-EDIT-NAV')
        self.target_user = User.objects.create_user(
            email='edit-nav-patient@test.com',
            password='PatientPass123!',
            role='patient',
            first_name='T',
            last_name='S',
            is_active=True,
        )
        self.client.force_login(self.admin_user)

    def test_edit_user_uses_breadcrumb_subnav(self):
        response = self.client.get(
            reverse('core:user_edit', kwargs={'user_id': self.target_user.id}),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'aria-label="Breadcrumb"')
        self.assertContains(response, 'rounded-xl border border-gray-200')
        self.assertNotContains(response, 'mb-4 flex items-center gap-2 text-sm text-gray-500')
        self.assertContains(response, 'Edit user')



class AdminUserAuditLogTests(TestCase):
    """Tests for the user audit log view."""

    def setUp(self):
        self.admin_user = User.objects.create_user(
            email='admin-auditlog@test.com',
            password='AdminPass123!',
            role='admin',
            is_staff=True,
            is_active=True,
        )
        _complete_staff_like_profile(self.admin_user, 'ADM-AUDL-001')

        self.target_user = User.objects.create_user(
            email='target-auditlog@test.com',
            password='TestPass123!',
            role='patient',
            is_active=True,
        )

        # Create some audit entries
        for action in ['activated', 'suspended', 'activated']:
            AccountProvisioningAudit.objects.create(
                actor=self.admin_user,
                target_user=self.target_user,
                action=action,
                ip_address='127.0.0.1',
            )

        self.client.force_login(self.admin_user)
        self.url = reverse('core:user_audit_log', kwargs={'user_id': self.target_user.id})

    def test_audit_log_renders(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'core/user_management/user_audit_log.html')

    def test_audit_log_shows_entries(self):
        response = self.client.get(self.url)
        self.assertContains(response, 'Activated')
        self.assertContains(response, 'Suspended')

    def test_audit_log_filters_by_action(self):
        response = self.client.get(self.url, {'action': 'activated'})
        self.assertEqual(response.status_code, 200)
        # Should have 2 activated entries
        self.assertEqual(len(response.context['audits']), 2)  # paginate_queryset wraps in Page, shows 2 on page after filter
        # Note: audit log was seeded with 'activated', 'suspended', 'activated' (3 entries)
        # Filtering by 'activated' should return 2 entries

    def test_audit_log_filters_by_date(self):
        response = self.client.get(self.url, {
            'date_from': timezone.now().date() - timedelta(days=1),
            'date_to': timezone.now().date() + timedelta(days=1),
        })
        self.assertEqual(response.status_code, 200)


class AdminUserExportCSVTests(TestCase):
    """Tests for the user CSV export functionality."""

    def setUp(self):
        self.admin_user = User.objects.create_user(
            email='admin-export@test.com',
            password='AdminPass123!',
            role='admin',
            is_staff=True,
            is_active=True,
        )
        _complete_staff_like_profile(self.admin_user, 'ADM-EXPT-001')

        for i in range(3):
            user = User.objects.create_user(
                email=f'export-user-{i}@test.com',
                password='TestPass123!',
                role='patient' if i % 2 == 0 else 'staff',
                is_active=True,
            )

        self.client.force_login(self.admin_user)
        self.url = reverse('core:user_export_csv')

    def test_export_returns_csv(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertIn('Content-Disposition', response)
        self.assertIn('.csv', response['Content-Disposition'])

    def test_export_contains_headers(self):
        response = self.client.get(self.url)
        content = response.content.decode('utf-8')
        self.assertIn('Email', content)
        self.assertIn('Role', content)
        self.assertIn('Status', content)

    def test_export_contains_user_data(self):
        response = self.client.get(self.url)
        content = response.content.decode('utf-8')
        self.assertIn('export-user-0@test.com', content)
        self.assertIn('export-user-1@test.com', content)

    def test_export_filters_by_role(self):
        response = self.client.get(self.url, {'role': 'student'})
        content = response.content.decode('utf-8')
        self.assertIn('export-user-0@test.com', content)
        self.assertNotIn('export-user-1@test.com', content)  # staff

    def test_export_respects_date_filter(self):
        response = self.client.get(self.url, {
            'date_from': (timezone.now() - timedelta(days=1)).strftime('%Y-%m-%d'),
        })
        self.assertEqual(response.status_code, 200)


class AdminStaleUserCleanupTests(TestCase):
    """Tests for the stale user cleanup functionality."""

    def setUp(self):
        self.admin_user = User.objects.create_user(
            email='admin-cleanup@test.com',
            password='AdminPass123!',
            role='admin',
            is_staff=True,
            is_active=True,
        )
        _complete_staff_like_profile(self.admin_user, 'ADM-CLNP-001')

        # Create a stale pending user (30+ days old, pending activation)
        self.stale_pending = User.objects.create_user(
            email='stale-pending@test.com',
            password='TestPass123!',
            role='patient',
            is_active=False,
            onboarding_status=User.ONBOARDING_STATUS.PENDING_ACTIVATION,
        )
        # Manually set date_joined to 31 days ago
        User.objects.filter(id=self.stale_pending.id).update(
            date_joined=timezone.now() - timedelta(days=31)
        )

        # Create a stale inactive user (no activity for 6+ months)
        self.stale_inactive = User.objects.create_user(
            email='stale-inactive@test.com',
            password='TestPass123!',
            role='patient',
            is_active=True,
        )
        User.objects.filter(id=self.stale_inactive.id).update(
            last_activity_at=timezone.now() - timedelta(days=200)
        )

        self.client.force_login(self.admin_user)
        self.url = reverse('core:user_cleanup_stale')

    def test_cleanup_page_shows_stale_users(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'stale-pending@test.com')
        self.assertContains(response, 'stale-inactive@test.com')

    def test_cleanup_action_deactivates_stale_pending(self):
        response = self.client.post(self.url, {
            'action': 'deactivate_stale',
            'deactivate_pending': '1',
        })
        self.assertRedirects(response, self.url)

        self.stale_pending.refresh_from_db()
        self.assertFalse(self.stale_pending.is_active)
        self.assertEqual(self.stale_pending.onboarding_status, User.ONBOARDING_STATUS.SUSPENDED)

    def test_cleanup_action_deactivates_stale_inactive(self):
        response = self.client.post(self.url, {
            'action': 'deactivate_stale',
            'deactivate_inactive': '1',
        })
        self.assertRedirects(response, self.url)

        self.stale_inactive.refresh_from_db()
        self.assertFalse(self.stale_inactive.is_active)

    def test_cleanup_creates_audit_logs(self):
        self.client.post(self.url, {
            'action': 'deactivate_stale',
            'deactivate_pending': '1',
            'deactivate_inactive': '1',
        })

        audits = AccountProvisioningAudit.objects.filter(
            target_user__in=[self.stale_pending, self.stale_inactive],
        )
        self.assertEqual(audits.count(), 2)


# ============================================================================
# Form Tests
# ============================================================================

class BulkUserActionFormTests(TestCase):
    """Tests for the BulkUserActionForm."""

    def test_valid_form(self):
        form = BulkUserActionForm({
            'action': 'activate',
            'user_ids': '1,2,3',
            'confirmation': True,
        })
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['user_ids'], [1, 2, 3])

    def test_invalid_action(self):
        form = BulkUserActionForm({
            'action': 'invalid',
            'user_ids': '1,2,3',
            'confirmation': True,
        })
        self.assertFalse(form.is_valid())

    def test_empty_user_ids(self):
        form = BulkUserActionForm({
            'action': 'activate',
            'user_ids': '',
            'confirmation': True,
        })
        self.assertFalse(form.is_valid())

    def test_missing_confirmation(self):
        form = BulkUserActionForm({
            'action': 'activate',
            'user_ids': '1,2,3',
            'confirmation': False,
        })
        self.assertFalse(form.is_valid())

    def test_single_user_id(self):
        form = BulkUserActionForm({
            'action': 'deactivate',
            'user_ids': '42',
            'confirmation': True,
        })
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['user_ids'], [42])


class UserExportFormTests(TestCase):
    """Tests for the UserExportForm."""

    def test_empty_form_is_valid(self):
        form = UserExportForm({})
        self.assertTrue(form.is_valid())

    def test_valid_role_filter(self):
        form = UserExportForm({'role': 'student'})
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['role'], 'student')

    def test_valid_status_filter(self):
        form = UserExportForm({'status': 'active'})
        self.assertTrue(form.is_valid())

    def test_valid_date_range(self):
        form = UserExportForm({
            'date_from': '2024-01-01',
            'date_to': '2024-12-31',
        })
        self.assertTrue(form.is_valid())

    def test_invalid_date(self):
        form = UserExportForm({'date_from': 'not-a-date'})
        self.assertFalse(form.is_valid())


# ============================================================================
# Integration Tests
# ============================================================================

@override_settings(
    AUTH_PASSWORD_VALIDATORS=[
        {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    ]
)
class UserManagementSoftDeleteIntegrationTests(TestCase):
    """Integration tests for soft-delete in the user management flow."""

    def setUp(self):
        self.admin_user = User.objects.create_user(
            email='admin-int@test.com',
            password='AdminPass123!',
            role='admin',
            is_staff=True,
            is_active=True,
        )
        _complete_staff_like_profile(self.admin_user, 'ADM-INT-001')

        self.target_user = User.objects.create_user(
            email='target-int@test.com',
            password='TestPass123!',
            role='patient',
            is_active=True,
        )

        self.client.force_login(self.admin_user)

    def test_user_list_excludes_deleted_by_default(self):
        self.target_user.soft_delete()
        response = self.client.get(reverse('core:user_management'))
        user_emails = [u.email for u in response.context['users']]
        self.assertNotIn(self.target_user.email, user_emails)

    def test_deleted_page_shows_deleted_users(self):
        self.target_user.soft_delete()
        response = self.client.get(reverse('core:deleted_user_management'))
        user_emails = [u.email for u in response.context['users']]
        self.assertIn(self.target_user.email, user_emails)

    def test_user_management_redirects_deleted_filter_to_deleted_page(self):
        response = self.client.get(reverse('core:user_management'), {'status': 'deleted'})
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('core:deleted_user_management'), response.url)

    def test_user_detail_shows_restore_button_for_deleted(self):
        self.target_user.soft_delete()
        response = self.client.get(
            reverse('core:user_detail', kwargs={'user_id': self.target_user.id})
        )
        self.assertContains(response, 'Restore User')

    def test_soft_deleted_user_cannot_login(self):
        self.target_user.soft_delete()
        login_success = self.client.login(
            email='target-int@test.com',
            password='TestPass123!',
        )
        self.assertFalse(login_success)

    def test_user_detail_shows_audit_log_link(self):
        response = self.client.get(
            reverse('core:user_detail', kwargs={'user_id': self.target_user.id})
        )
        self.assertContains(response, 'View Audit Log')
