"""
Pharmacy app – Medicine create/edit tests.

Coverage:
  - GET/POST permissions (admin/staff can access, student cannot)
  - Successful medicine creation (no opening stock)
  - Successful medicine creation with opening stock
  - Audit-log entries created on create
  - Threshold validation (reorder_level >= max_stock_level rejected)
  - Duplicate name+strength detection
  - Opening-stock cross-field validation (missing batch, missing expiry, past expiry)
"""

import datetime

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import Medicine, MedicineCategory, Batch, AuditLog

# ─── Helper: strip ProfileCompleteMiddleware during tests ───────────────────
# It redirects users with incomplete profiles to the profile-required page,
# which would interfere with tests that use non-admin roles.

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
    # ProfileCompleteMiddleware intentionally removed
]

CREATE_URL = reverse('pharmacy:medicine_create')


def _make_user(role='admin', email=None, **kwargs):
    """Create a user with the given role."""
    from django.contrib.auth import get_user_model
    User = get_user_model()
    email = email or f'{role}@test.example'
    user = User.objects.create_user(email=email, password='test1234', role=role, **kwargs)
    return user


def _valid_post(overrides=None):
    """Return a valid POST payload for medicine creation."""
    data = {
        'name': 'Paracetamol',
        'generic_name': 'Paracetamol',
        'brand_name': 'Biogesic',
        'description': 'Pain reliever',
        'unit': 'tablet',
        'strength': '500mg',
        'reorder_level': 10,
        'max_stock_level': 500,
        'requires_prescription': False,
        'is_active': True,
    }
    if overrides:
        data.update(overrides)
    return data


@override_settings(MIDDLEWARE=STRIPPED_MIDDLEWARE)
class MedicineCreatePermissionTest(TestCase):
    """Only admin and staff can create medicines; students are redirected."""

    def test_anonymous_user_is_forbidden(self):
        # RoleMiddleware returns 403 for unauthenticated users
        # when a view requires a specific role.
        response = self.client.get(CREATE_URL)
        self.assertEqual(response.status_code, 403)

    def test_student_is_forbidden(self):
        # RoleMiddleware returns 403 for roles not in required_roles.
        user = _make_user(role='student', email='student@test.example')
        self.client.force_login(user)
        response = self.client.get(CREATE_URL)
        self.assertEqual(response.status_code, 403)

    def test_staff_can_access(self):
        user = _make_user(role='staff', email='staff@test.example')
        self.client.force_login(user)
        response = self.client.get(CREATE_URL)
        self.assertEqual(response.status_code, 200)

    def test_admin_can_access(self):
        user = _make_user(role='admin', email='admin@test.example')
        self.client.force_login(user)
        response = self.client.get(CREATE_URL)
        self.assertEqual(response.status_code, 200)


@override_settings(MIDDLEWARE=STRIPPED_MIDDLEWARE)
class MedicineCreateTest(TestCase):
    """Tests for successful and failed medicine creation."""

    def setUp(self):
        self.user = _make_user(role='admin')
        self.client.force_login(self.user)
        self.category = MedicineCategory.objects.create(name='Analgesic')

    # ── GET ─────────────────────────────────────────────────────────────

    def test_get_renders_form(self):
        response = self.client.get(CREATE_URL)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'pharmacy/medicine_form.html')
        self.assertIn('form', response.context)

    # ── Successful create (no opening stock) ────────────────────────────

    def test_valid_post_creates_medicine(self):
        response = self.client.post(CREATE_URL, _valid_post())
        self.assertEqual(Medicine.objects.count(), 1)
        med = Medicine.objects.first()
        self.assertEqual(med.name, 'Paracetamol')
        self.assertRedirects(
            response,
            reverse('pharmacy:medicine_detail', kwargs={'medicine_id': med.pk}),
            fetch_redirect_response=False,
        )

    def test_valid_post_writes_medicine_added_audit_log(self):
        self.client.post(CREATE_URL, _valid_post())
        self.assertTrue(
            AuditLog.objects.filter(action='medicine_added').exists(),
            'medicine_added audit log entry should be created',
        )
        log = AuditLog.objects.get(action='medicine_added')
        self.assertEqual(log.performed_by, self.user)
        self.assertEqual(log.medicine, Medicine.objects.first())

    def test_valid_post_no_batch_created_without_opening_stock(self):
        self.client.post(CREATE_URL, _valid_post())
        self.assertEqual(Batch.objects.count(), 0)

    # ── Successful create with opening stock ────────────────────────────

    def test_create_with_opening_stock_creates_batch(self):
        future = (timezone.now().date() + datetime.timedelta(days=365)).isoformat()
        payload = _valid_post({
            'opening_quantity': 50,
            'opening_batch_number': 'BATCH-001',
            'opening_unit_cost': '5.50',
            'opening_expiry_date': future,
        })
        self.client.post(CREATE_URL, payload)
        self.assertEqual(Batch.objects.count(), 1)
        batch = Batch.objects.first()
        self.assertEqual(batch.quantity, 50)
        self.assertEqual(batch.batch_number, 'BATCH-001')

    def test_create_with_opening_stock_writes_stock_in_audit(self):
        future = (timezone.now().date() + datetime.timedelta(days=365)).isoformat()
        payload = _valid_post({
            'opening_quantity': 50,
            'opening_batch_number': 'BATCH-001',
            'opening_expiry_date': future,
        })
        self.client.post(CREATE_URL, payload)
        self.assertTrue(
            AuditLog.objects.filter(action='stock_in').exists(),
            'stock_in audit entry should be created with opening stock',
        )
        log = AuditLog.objects.get(action='stock_in')
        self.assertEqual(log.quantity, 50)


@override_settings(MIDDLEWARE=STRIPPED_MIDDLEWARE)
class MedicineFormValidationTest(TestCase):
    """Tests for all custom clean() rules on MedicineForm."""

    def setUp(self):
        self.user = _make_user(role='admin')
        self.client.force_login(self.user)

    # ── Threshold validation ─────────────────────────────────────────────

    def test_reorder_level_equal_to_max_is_invalid(self):
        payload = _valid_post({'reorder_level': 100, 'max_stock_level': 100})
        response = self.client.post(CREATE_URL, payload)
        self.assertEqual(response.status_code, 200)   # re-renders form with errors
        self.assertEqual(Medicine.objects.count(), 0)
        self.assertFormError(
            response.context['form'], 'reorder_level',
            'Reorder level must be less than the maximum stock level.',
        )

    def test_reorder_level_greater_than_max_is_invalid(self):
        payload = _valid_post({'reorder_level': 600, 'max_stock_level': 500})
        response = self.client.post(CREATE_URL, payload)
        self.assertEqual(response.status_code, 200)
        self.assertFormError(
            response.context['form'], 'reorder_level',
            'Reorder level must be less than the maximum stock level.',
        )

    def test_valid_thresholds_accepted(self):
        self.client.post(CREATE_URL, _valid_post({'reorder_level': 10, 'max_stock_level': 500}))
        self.assertEqual(Medicine.objects.count(), 1)

    # ── Duplicate detection ──────────────────────────────────────────────

    def test_duplicate_name_and_strength_rejected(self):
        Medicine.objects.create(
            name='Paracetamol', strength='500mg', unit='tablet',
            reorder_level=10, max_stock_level=500,
        )
        response = self.client.post(CREATE_URL, _valid_post({'strength': '500mg'}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Medicine.objects.count(), 1)
        self.assertTrue(response.context['form'].errors.get('name'))

    def test_same_name_different_strength_is_allowed(self):
        Medicine.objects.create(
            name='Paracetamol', strength='500mg', unit='tablet',
            reorder_level=10, max_stock_level=500,
        )
        self.client.post(CREATE_URL, _valid_post({'name': 'Paracetamol', 'strength': '1000mg'}))
        self.assertEqual(Medicine.objects.count(), 2)

    def test_duplicate_check_is_case_insensitive(self):
        Medicine.objects.create(
            name='paracetamol', strength='500mg', unit='tablet',
            reorder_level=10, max_stock_level=500,
        )
        response = self.client.post(
            CREATE_URL, _valid_post({'name': 'PARACETAMOL', 'strength': '500mg'})
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Medicine.objects.count(), 1)

    def test_same_name_no_strength_duplicate_rejected(self):
        Medicine.objects.create(
            name='Ibuprofen', strength='', unit='tablet',
            reorder_level=10, max_stock_level=500,
        )
        response = self.client.post(
            CREATE_URL, _valid_post({'name': 'Ibuprofen', 'strength': ''})
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Medicine.objects.count(), 1)

    # ── Opening stock cross-field validation ─────────────────────────────

    def test_opening_qty_without_batch_number_is_invalid(self):
        future = (timezone.now().date() + datetime.timedelta(days=365)).isoformat()
        payload = _valid_post({
            'opening_quantity': 50,
            'opening_batch_number': '',
            'opening_expiry_date': future,
        })
        response = self.client.post(CREATE_URL, payload)
        self.assertEqual(response.status_code, 200)
        self.assertFormError(
            response.context['form'], 'opening_batch_number',
            'Batch number is required when providing opening stock.',
        )

    def test_opening_qty_without_expiry_is_invalid(self):
        payload = _valid_post({
            'opening_quantity': 50,
            'opening_batch_number': 'BATCH-001',
            'opening_expiry_date': '',
        })
        response = self.client.post(CREATE_URL, payload)
        self.assertEqual(response.status_code, 200)
        self.assertFormError(
            response.context['form'], 'opening_expiry_date',
            'Expiry date is required when providing opening stock.',
        )

    def test_opening_stock_with_past_expiry_is_invalid(self):
        past = (timezone.now().date() - datetime.timedelta(days=1)).isoformat()
        payload = _valid_post({
            'opening_quantity': 50,
            'opening_batch_number': 'BATCH-001',
            'opening_expiry_date': past,
        })
        response = self.client.post(CREATE_URL, payload)
        self.assertEqual(response.status_code, 200)
        self.assertFormError(
            response.context['form'], 'opening_expiry_date',
            'Expiry date must be a date in the future.',
        )

    def test_opening_stock_with_today_expiry_is_invalid(self):
        today = timezone.now().date().isoformat()
        payload = _valid_post({
            'opening_quantity': 50,
            'opening_batch_number': 'BATCH-001',
            'opening_expiry_date': today,
        })
        response = self.client.post(CREATE_URL, payload)
        self.assertEqual(response.status_code, 200)
        self.assertFormError(
            response.context['form'], 'opening_expiry_date',
            'Expiry date must be a date in the future.',
        )
