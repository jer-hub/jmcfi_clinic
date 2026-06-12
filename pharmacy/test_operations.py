"""View-level workflow tests for dispensing, adjustments, and PO actions."""

import datetime
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from pharmacy.models import (
    AuditLog,
    Batch,
    Dispensing,
    Medicine,
    PurchaseOrder,
    PurchaseOrderItem,
    StockAdjustment,
    Supplier,
)
from pharmacy.test_helpers import make_user, pharmacy_test_settings


@pharmacy_test_settings
class DispensingCreateViewTest(TestCase):
    def setUp(self):
        self.staff = make_user(role='staff', email='op-disp-staff@test.example')
        self.patient = make_user(role='student', email='op-disp-patient@test.example')
        self.client.force_login(self.staff)
        self.medicine = Medicine.objects.create(
            name='View Disp Med',
            unit='tablet',
            reorder_level=1,
            max_stock_level=100,
        )
        future = timezone.now().date() + datetime.timedelta(days=365)
        self.batch = Batch.objects.create(
            medicine=self.medicine,
            batch_number='VIEW-D1',
            quantity=8,
            expiry_date=future,
        )
        self.url = reverse('pharmacy:dispensing_create')

    def test_post_dispense_decrements_stock(self):
        response = self.client.post(self.url, {
            'patient': self.patient.pk,
            'medicine': self.medicine.pk,
            'batch': self.batch.pk,
            'quantity': 3,
            'prescription_reference': '',
            'prescribing_doctor': '',
            'reason': 'Test dispense',
        })
        self.assertRedirects(response, reverse('pharmacy:dispensing_list'), fetch_redirect_response=False)
        self.batch.refresh_from_db()
        self.assertEqual(self.batch.quantity, 5)
        self.assertEqual(Dispensing.objects.count(), 1)

    def test_post_insufficient_stock_shows_error(self):
        response = self.client.post(self.url, {
            'patient': self.patient.pk,
            'medicine': self.medicine.pk,
            'batch': self.batch.pk,
            'quantity': 50,
            'prescription_reference': '',
            'prescribing_doctor': '',
            'reason': '',
        })
        self.assertEqual(response.status_code, 200)
        self.batch.refresh_from_db()
        self.assertEqual(self.batch.quantity, 8)
        self.assertEqual(Dispensing.objects.count(), 0)

    def test_post_staff_as_patient_rejected(self):
        response = self.client.post(self.url, {
            'patient': self.staff.pk,
            'medicine': self.medicine.pk,
            'batch': self.batch.pk,
            'quantity': 1,
            'prescription_reference': '',
            'prescribing_doctor': '',
            'reason': '',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Dispensing.objects.count(), 0)
        self.assertContains(response, 'valid patient')

    def test_post_rx_medicine_without_prescription_fails(self):
        self.medicine.requires_prescription = True
        self.medicine.save(update_fields=['requires_prescription'])
        response = self.client.post(self.url, {
            'patient': self.patient.pk,
            'medicine': self.medicine.pk,
            'batch': self.batch.pk,
            'quantity': 1,
            'prescription_reference': '',
            'prescribing_doctor': '',
            'reason': '',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Dispensing.objects.count(), 0)
        self.assertContains(response, 'prescription')

    def test_post_medicine_batch_mismatch_fails(self):
        other = Medicine.objects.create(
            name='Other Med',
            unit='tablet',
            reorder_level=1,
            max_stock_level=100,
        )
        future = timezone.now().date() + datetime.timedelta(days=200)
        Batch.objects.create(
            medicine=other,
            batch_number='OTHER-B1',
            quantity=5,
            expiry_date=future,
        )
        response = self.client.post(self.url, {
            'patient': self.patient.pk,
            'medicine': other.pk,
            'batch': self.batch.pk,
            'quantity': 1,
            'prescription_reference': '',
            'prescribing_doctor': '',
            'reason': '',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Dispensing.objects.count(), 0)
        self.assertContains(response, 'does not belong')

    def test_patient_query_prefill_renders_selected_patient(self):
        response = self.client.get(f'{self.url}?patient={self.patient.pk}')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'dispensing-selected-patient')
        self.assertContains(response, self.patient.email)

    def test_form_renders_sectioned_layout_and_confirm_modal(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'dispensing-patient-search')
        self.assertContains(response, 'Stock summary')
        self.assertContains(response, 'Confirm Dispense')
        self.assertContains(response, 'Recent dispensings')


@pharmacy_test_settings
class StockAdjustmentCreateViewTest(TestCase):
    def setUp(self):
        self.staff = make_user(role='staff', email='op-adj-staff@test.example')
        self.client.force_login(self.staff)
        self.medicine = Medicine.objects.create(
            name='View Adj Med',
            unit='tablet',
            reorder_level=1,
            max_stock_level=50,
        )
        future = timezone.now().date() + datetime.timedelta(days=300)
        self.batch = Batch.objects.create(
            medicine=self.medicine,
            batch_number='VIEW-A1',
            quantity=15,
            expiry_date=future,
        )
        self.url = reverse('pharmacy:adjustment_create')

    def test_post_adjustment_updates_batch_and_audit(self):
        response = self.client.post(self.url, {
            'batch': self.batch.pk,
            'quantity_change': -5,
            'reason': 'damaged',
            'notes': 'Broken seal',
        })
        self.assertRedirects(response, reverse('pharmacy:adjustment_list'), fetch_redirect_response=False)
        self.batch.refresh_from_db()
        self.assertEqual(self.batch.quantity, 10)
        self.assertEqual(StockAdjustment.objects.count(), 1)
        self.assertTrue(AuditLog.objects.filter(action='adjustment').exists())


@pharmacy_test_settings
class PurchaseOrderActionViewTest(TestCase):
    def setUp(self):
        self.staff = make_user(role='staff', email='op-po-staff@test.example')
        self.client.force_login(self.staff)
        self.supplier = Supplier.objects.create(name='View Supplier')
        self.medicine = Medicine.objects.create(
            name='View PO Med',
            unit='tablet',
            reorder_level=1,
            max_stock_level=100,
        )
        self.po = PurchaseOrder.objects.create(
            supplier=self.supplier,
            ordered_by=self.staff,
            status='submitted',
        )
        self.item = PurchaseOrderItem.objects.create(
            purchase_order=self.po,
            medicine=self.medicine,
            quantity_ordered=7,
            unit_cost=Decimal('3.00'),
        )

    def test_approve_post_updates_status(self):
        url = reverse('pharmacy:purchase_order_approve', kwargs={'order_id': self.po.pk})
        response = self.client.post(url)
        self.assertRedirects(
            response,
            reverse('pharmacy:purchase_order_detail', kwargs={'order_id': self.po.pk}),
            fetch_redirect_response=False,
        )
        self.po.refresh_from_db()
        self.assertEqual(self.po.status, 'approved')

    def test_receive_post_creates_stock(self):
        self.po.status = 'approved'
        self.po.save(update_fields=['status'])
        url = reverse('pharmacy:purchase_order_receive', kwargs={'order_id': self.po.pk})
        response = self.client.post(url)
        self.assertRedirects(
            response,
            reverse('pharmacy:purchase_order_detail', kwargs={'order_id': self.po.pk}),
            fetch_redirect_response=False,
        )
        self.po.refresh_from_db()
        self.assertEqual(self.po.status, 'received')
        self.assertTrue(
            Batch.objects.filter(
                medicine=self.medicine,
                batch_number=f'PO-{self.po.order_number}-{self.item.pk}',
            ).exists()
        )

    def test_approve_htmx_returns_toast_trigger(self):
        url = reverse('pharmacy:purchase_order_approve', kwargs={'order_id': self.po.pk})
        response = self.client.post(url, HTTP_HX_REQUEST='true')
        self.assertEqual(response.status_code, 200)
        self.assertIn('HX-Trigger', response)
        self.assertIn('user-toast', response['HX-Trigger'])
        self.assertIn('HX-Redirect', response)
