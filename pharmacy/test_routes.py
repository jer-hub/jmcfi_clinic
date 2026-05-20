"""Complete pharmacy route permission matrix (Pharmacy Phase 5)."""

import datetime

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from pharmacy.models import (
    Batch,
    Medicine,
    MedicineCategory,
    PurchaseOrder,
    Supplier,
)
from pharmacy.test_helpers import make_user, pharmacy_test_settings


@pharmacy_test_settings
class PharmacyFullRouteAccessTest(TestCase):
    """Staff may access all pharmacy endpoints; others are denied."""

    @classmethod
    def setUpTestData(cls):
        cls.staff = make_user(role='staff', email='routes-staff@test.example')
        cls.student = make_user(role='student', email='routes-student@test.example')
        cls.doctor = make_user(role='doctor', email='routes-doctor@test.example')
        cls.admin = make_user(role='admin', email='routes-admin@test.example')

        cls.category = MedicineCategory.objects.create(name='Route Cat')
        cls.medicine = Medicine.objects.create(
            name='Route Med',
            category=cls.category,
            unit='tablet',
            reorder_level=1,
            max_stock_level=50,
        )
        future = timezone.now().date() + datetime.timedelta(days=200)
        cls.batch = Batch.objects.create(
            medicine=cls.medicine,
            batch_number='ROUTE-B1',
            quantity=5,
            expiry_date=future,
        )
        cls.supplier = Supplier.objects.create(name='Route Supplier')
        cls.order = PurchaseOrder.objects.create(
            supplier=cls.supplier,
            ordered_by=cls.staff,
            status='draft',
        )

    def _staff_get_ok(self, url_name, **kwargs):
        self.client.force_login(self.staff)
        response = self.client.get(reverse(url_name, kwargs=kwargs))
        self.assertEqual(response.status_code, 200, url_name)

    def _forbidden_get(self, user, url_name, **kwargs):
        self.client.force_login(user)
        response = self.client.get(reverse(url_name, kwargs=kwargs))
        self.assertEqual(response.status_code, 403, f'{url_name} for {user.role}')

    def test_staff_can_access_all_list_and_form_routes(self):
        routes = [
            ('pharmacy:dashboard', {}),
            ('pharmacy:medicine_list', {}),
            ('pharmacy:medicine_create', {}),
            ('pharmacy:medicine_detail', {'medicine_id': self.medicine.pk}),
            ('pharmacy:medicine_edit', {'medicine_id': self.medicine.pk}),
            ('pharmacy:category_list', {}),
            ('pharmacy:category_create', {}),
            ('pharmacy:category_edit', {'category_id': self.category.pk}),
            ('pharmacy:category_delete', {'category_id': self.category.pk}),
            ('pharmacy:batch_list', {}),
            ('pharmacy:batch_create', {}),
            ('pharmacy:batch_edit', {'batch_id': self.batch.pk}),
            ('pharmacy:supplier_list', {}),
            ('pharmacy:supplier_create', {}),
            ('pharmacy:supplier_edit', {'supplier_id': self.supplier.pk}),
            ('pharmacy:purchase_order_list', {}),
            ('pharmacy:purchase_order_create', {}),
            ('pharmacy:purchase_order_detail', {'order_id': self.order.pk}),
            ('pharmacy:dispensing_list', {}),
            ('pharmacy:dispensing_create', {}),
            ('pharmacy:adjustment_list', {}),
            ('pharmacy:adjustment_create', {}),
            ('pharmacy:audit_log_list', {}),
            ('pharmacy:compliance_report', {}),
            ('pharmacy:cost_analysis', {}),
            ('pharmacy:api_batches_for_medicine', {'medicine_id': self.medicine.pk}),
        ]
        for name, kwargs in routes:
            self._staff_get_ok(name, **kwargs)

    def test_student_forbidden_on_operational_routes(self):
        routes = [
            ('pharmacy:dispensing_create', {}),
            ('pharmacy:adjustment_create', {}),
            ('pharmacy:purchase_order_create', {}),
            ('pharmacy:api_batches_for_medicine', {'medicine_id': self.medicine.pk}),
        ]
        for name, kwargs in routes:
            self._forbidden_get(self.student, name, **kwargs)

    def test_doctor_forbidden_on_inventory_routes(self):
        routes = [
            ('pharmacy:medicine_create', {}),
            ('pharmacy:batch_create', {}),
            ('pharmacy:supplier_create', {}),
        ]
        for name, kwargs in routes:
            self._forbidden_get(self.doctor, name, **kwargs)
