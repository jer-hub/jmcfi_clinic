"""Procurement UX tests — suppliers and purchase orders."""

import datetime
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from pharmacy.models import Medicine, PurchaseOrder, PurchaseOrderItem, Supplier
from pharmacy.test_helpers import make_user, pharmacy_test_settings


@pharmacy_test_settings
class SupplierFormTest(TestCase):
    def setUp(self):
        self.staff = make_user(role='staff', email='proc-sup-staff@test.example')
        self.client.force_login(self.staff)
        self.create_url = reverse('pharmacy:supplier_create')

    def test_duplicate_supplier_name_rejected(self):
        Supplier.objects.create(name='Acme Pharma', email='a@acme.test')
        response = self.client.post(self.create_url, {
            'name': 'acme pharma',
            'contact_person': '',
            'email': 'b@acme.test',
            'phone': '',
            'address': '',
            'notes': '',
            'is_active': True,
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'already exists')
        self.assertEqual(Supplier.objects.filter(name__iexact='Acme Pharma').count(), 1)

    def test_supplier_requires_contact_method(self):
        response = self.client.post(self.create_url, {
            'name': 'No Contact Vendor',
            'contact_person': '',
            'email': '',
            'phone': '',
            'address': '',
            'notes': '',
            'is_active': True,
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'email or phone')


@pharmacy_test_settings
class SupplierDetailTest(TestCase):
    def setUp(self):
        self.staff = make_user(role='staff', email='proc-det-staff@test.example')
        self.client.force_login(self.staff)
        self.supplier = Supplier.objects.create(
            name='Detail Supplier',
            email='detail@supplier.test',
        )
        self.order = PurchaseOrder.objects.create(
            supplier=self.supplier,
            ordered_by=self.staff,
            status='draft',
        )
        PurchaseOrderItem.objects.create(
            purchase_order=self.order,
            medicine=Medicine.objects.create(
                name='Detail Med', unit='tablet', reorder_level=1, max_stock_level=50,
            ),
            quantity_ordered=5,
            unit_cost=Decimal('2.00'),
        )

    def test_supplier_detail_renders_order_history(self):
        url = reverse('pharmacy:supplier_detail', kwargs={'supplier_id': self.supplier.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Detail Supplier')
        self.assertContains(response, f'PO-{self.order.order_number}')
        self.assertContains(response, 'New Purchase Order')


@pharmacy_test_settings
class PurchaseOrderCreatePrefillTest(TestCase):
    def setUp(self):
        self.staff = make_user(role='staff', email='proc-po-staff@test.example')
        self.client.force_login(self.staff)
        self.supplier = Supplier.objects.create(
            name='PO Supplier',
            email='po@supplier.test',
        )
        self.medicine = Medicine.objects.create(
            name='Low Stock Med',
            unit='tablet',
            reorder_level=10,
            max_stock_level=100,
            cached_non_expired_stock=3,
            stock_cache_updated_at=timezone.now(),
        )

    def test_supplier_query_prefill(self):
        url = reverse('pharmacy:purchase_order_create') + f'?supplier={self.supplier.pk}'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'PO Supplier')
        self.assertContains(response, f'value="{self.supplier.pk}"', html=False)

    def test_reorder_prefill_renders_line_items(self):
        url = reverse('pharmacy:purchase_order_create') + '?reorder=1'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Reorder prefill')
        self.assertContains(response, 'Low Stock Med')

    def test_formset_duplicate_medicine_rejected(self):
        url = reverse('pharmacy:purchase_order_create')
        response = self.client.post(url, {
            'supplier': self.supplier.pk,
            'order_date': timezone.now().date().isoformat(),
            'expected_delivery': '',
            'notes': '',
            'items-TOTAL_FORMS': '2',
            'items-INITIAL_FORMS': '0',
            'items-MIN_NUM_FORMS': '0',
            'items-MAX_NUM_FORMS': '1000',
            'items-0-medicine': self.medicine.pk,
            'items-0-quantity_ordered': '5',
            'items-0-unit_cost': '1.00',
            'items-1-medicine': self.medicine.pk,
            'items-1-quantity_ordered': '3',
            'items-1-unit_cost': '2.00',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'only appear once')
        self.assertEqual(PurchaseOrder.objects.count(), 0)


@pharmacy_test_settings
class PurchaseOrderEditTest(TestCase):
    def setUp(self):
        self.staff = make_user(role='staff', email='proc-edit-staff@test.example')
        self.client.force_login(self.staff)
        self.supplier = Supplier.objects.create(name='Edit Supplier', email='edit@test.example')
        self.medicine = Medicine.objects.create(
            name='Edit Med', unit='tablet', reorder_level=1, max_stock_level=50,
        )
        self.order = PurchaseOrder.objects.create(
            supplier=self.supplier,
            ordered_by=self.staff,
            status='draft',
        )
        self.item = PurchaseOrderItem.objects.create(
            purchase_order=self.order,
            medicine=self.medicine,
            quantity_ordered=4,
            unit_cost=Decimal('5.00'),
        )
        self.edit_url = reverse('pharmacy:purchase_order_edit', kwargs={'order_id': self.order.pk})

    def test_draft_edit_updates_quantity(self):
        order_date = self.order.order_date
        if hasattr(order_date, 'date'):
            order_date = order_date.date()
        response = self.client.post(self.edit_url, {
            'supplier': self.supplier.pk,
            'order_date': order_date.isoformat(),
            'expected_delivery': '',
            'notes': 'Updated',
            'items-TOTAL_FORMS': '1',
            'items-INITIAL_FORMS': '1',
            'items-MIN_NUM_FORMS': '0',
            'items-MAX_NUM_FORMS': '1000',
            'items-0-id': self.item.pk,
            'items-0-medicine': self.medicine.pk,
            'items-0-quantity_ordered': '9',
            'items-0-unit_cost': '5.00',
        })
        self.assertRedirects(
            response,
            reverse('pharmacy:purchase_order_detail', kwargs={'order_id': self.order.pk}),
            fetch_redirect_response=False,
        )
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity_ordered, 9)

    def test_non_draft_edit_blocked(self):
        self.order.status = 'approved'
        self.order.save(update_fields=['status'])
        response = self.client.get(self.edit_url)
        self.assertRedirects(
            response,
            reverse('pharmacy:purchase_order_detail', kwargs={'order_id': self.order.pk}),
            fetch_redirect_response=False,
        )
