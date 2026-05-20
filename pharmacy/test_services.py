"""Service-layer and workflow tests (Pharmacy Phase 5)."""

import datetime
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
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
from pharmacy.services.orders import approve_purchase_order, receive_purchase_order
from pharmacy.services.reports import (
    build_dashboard_context,
    dispensing_totals_since,
    procurement_totals_since,
)
from pharmacy.services.stock import (
    apply_stock_adjustment,
    dispense_and_deduct,
    receive_po_line_item,
)
from pharmacy.services.stock_snapshot import refresh_medicine_stock_cache
from pharmacy.test_helpers import make_user


class DispenseServiceTest(TestCase):
    def setUp(self):
        self.staff = make_user(role='staff', email='svc-disp-staff@test.example')
        self.patient = make_user(role='student', email='svc-disp-patient@test.example')
        self.medicine = Medicine.objects.create(
            name='Dispense Med',
            unit='tablet',
            reorder_level=5,
            max_stock_level=100,
        )
        future = timezone.now().date() + datetime.timedelta(days=180)
        self.batch = Batch.objects.create(
            medicine=self.medicine,
            batch_number='DISP-001',
            quantity=10,
            unit_cost=Decimal('2.50'),
            expiry_date=future,
        )

    def test_successful_dispense_decrements_stock_and_persists_record(self):
        dispensing = Dispensing(
            patient=self.patient,
            batch=self.batch,
            quantity=3,
        )
        dispense_and_deduct(dispensing, self.staff)

        self.batch.refresh_from_db()
        self.assertEqual(self.batch.quantity, 7)
        self.assertEqual(Dispensing.objects.count(), 1)
        saved = Dispensing.objects.get()
        self.assertEqual(saved.quantity, 3)
        self.assertEqual(saved.dispensed_by, self.staff)

    def test_successful_dispense_writes_dispensed_audit_log(self):
        dispensing = Dispensing(
            patient=self.patient,
            batch=self.batch,
            quantity=1,
        )
        dispense_and_deduct(dispensing, self.staff)

        log = AuditLog.objects.get(action='dispensed')
        self.assertEqual(log.performed_by, self.staff)
        self.assertEqual(log.quantity, 1)
        self.assertEqual(log.medicine, self.medicine)


class StockAdjustmentServiceTest(TestCase):
    def setUp(self):
        self.staff = make_user(role='staff', email='svc-adj-staff@test.example')
        self.medicine = Medicine.objects.create(
            name='Adjust Med',
            unit='tablet',
            reorder_level=1,
            max_stock_level=50,
        )
        future = timezone.now().date() + datetime.timedelta(days=365)
        self.batch = Batch.objects.create(
            medicine=self.medicine,
            batch_number='ADJ-001',
            quantity=20,
            expiry_date=future,
        )

    def test_positive_adjustment_increases_quantity(self):
        adjustment = StockAdjustment(
            batch=self.batch,
            quantity_change=5,
            reason='correction',
        )
        apply_stock_adjustment(adjustment, self.staff)

        self.batch.refresh_from_db()
        self.assertEqual(self.batch.quantity, 25)
        self.assertTrue(AuditLog.objects.filter(action='adjustment').exists())

    def test_negative_adjustment_within_stock_succeeds(self):
        adjustment = StockAdjustment(
            batch=self.batch,
            quantity_change=-8,
            reason='damaged',
        )
        apply_stock_adjustment(adjustment, self.staff)

        self.batch.refresh_from_db()
        self.assertEqual(self.batch.quantity, 12)

    def test_negative_adjustment_beyond_stock_raises(self):
        adjustment = StockAdjustment(
            batch=self.batch,
            quantity_change=-25,
            reason='damaged',
        )
        with self.assertRaises(ValidationError):
            apply_stock_adjustment(adjustment, self.staff)
        self.batch.refresh_from_db()
        self.assertEqual(self.batch.quantity, 20)
        self.assertEqual(StockAdjustment.objects.count(), 0)

    def test_expired_reason_writes_expired_disposed_audit(self):
        adjustment = StockAdjustment(
            batch=self.batch,
            quantity_change=-2,
            reason='expired',
        )
        apply_stock_adjustment(adjustment, self.staff)
        self.assertTrue(AuditLog.objects.filter(action='expired_disposed').exists())


class PurchaseOrderServiceTest(TestCase):
    def setUp(self):
        self.staff = make_user(role='staff', email='svc-po-staff@test.example')
        self.supplier = Supplier.objects.create(name='PO Supplier')
        self.medicine = Medicine.objects.create(
            name='PO Med',
            unit='tablet',
            reorder_level=1,
            max_stock_level=100,
        )

    def _approved_order_with_item(self, qty=10):
        po = PurchaseOrder.objects.create(
            supplier=self.supplier,
            ordered_by=self.staff,
            status='approved',
        )
        item = PurchaseOrderItem.objects.create(
            purchase_order=po,
            medicine=self.medicine,
            quantity_ordered=qty,
            unit_cost=Decimal('4.00'),
        )
        return po, item

    def test_approve_succeeds_for_draft_and_submitted_only(self):
        for status in ('draft', 'submitted'):
            po = PurchaseOrder.objects.create(
                supplier=self.supplier,
                ordered_by=self.staff,
                status=status,
            )
            self.assertTrue(approve_purchase_order(po, self.staff))
            po.refresh_from_db()
            self.assertEqual(po.status, 'approved')
            self.assertEqual(po.approved_by, self.staff)

    def test_approve_fails_for_received_order(self):
        po, _ = self._approved_order_with_item()
        po.status = 'received'
        po.save(update_fields=['status'])
        self.assertFalse(approve_purchase_order(po, self.staff))

    def test_receive_creates_batch_and_updates_order(self):
        po, item = self._approved_order_with_item(qty=15)
        self.assertTrue(receive_purchase_order(po, self.staff))

        po.refresh_from_db()
        item.refresh_from_db()
        self.assertEqual(po.status, 'received')
        self.assertIsNotNone(po.received_date)
        self.assertEqual(item.quantity_received, 15)

        batch = Batch.objects.get(
            medicine=self.medicine,
            batch_number=f'PO-{po.order_number}-{item.pk}',
        )
        self.assertEqual(batch.quantity, 15)
        self.assertTrue(AuditLog.objects.filter(action='order_received').exists())
        self.assertTrue(AuditLog.objects.filter(action='stock_in').exists())

    def test_receive_fails_when_not_approved(self):
        po = PurchaseOrder.objects.create(
            supplier=self.supplier,
            ordered_by=self.staff,
            status='draft',
        )
        PurchaseOrderItem.objects.create(
            purchase_order=po,
            medicine=self.medicine,
            quantity_ordered=5,
            unit_cost=Decimal('1.00'),
        )
        self.assertFalse(receive_purchase_order(po, self.staff))
        self.assertEqual(Batch.objects.count(), 0)

    def test_receive_po_line_item_increments_existing_batch(self):
        po, item = self._approved_order_with_item(qty=10)
        receive_po_line_item(po, item, self.staff)
        batch = Batch.objects.get(
            medicine=self.medicine,
            batch_number=f'PO-{po.order_number}-{item.pk}',
        )
        self.assertEqual(batch.quantity, 10)

        receive_po_line_item(po, item, self.staff)
        batch.refresh_from_db()
        self.assertEqual(batch.quantity, 20)


class DashboardReportsTest(TestCase):
    def setUp(self):
        self.staff = make_user(role='staff', email='svc-dash-staff@test.example')
        self.today = timezone.now().date()
        self.month_start = self.today.replace(day=1)

    def test_dispensing_totals_since_aggregates_quantity_and_cost(self):
        med = Medicine.objects.create(name='Report Med', unit='tablet', reorder_level=1, max_stock_level=50)
        future = self.today + datetime.timedelta(days=200)
        batch = Batch.objects.create(
            medicine=med,
            batch_number='RPT-1',
            quantity=100,
            unit_cost=Decimal('10.00'),
            expiry_date=future,
        )
        patient = make_user(role='student', email='svc-dash-patient@test.example')
        Dispensing.objects.create(
            patient=patient,
            dispensed_by=self.staff,
            batch=batch,
            quantity=4,
            dispensed_at=timezone.now(),
        )

        totals = dispensing_totals_since(self.month_start)
        self.assertEqual(totals['total_qty'], 4)
        self.assertEqual(totals['total_cost'], Decimal('40.00'))

    def test_procurement_totals_since_only_counts_received_orders(self):
        supplier = Supplier.objects.create(name='Report Supplier')
        med = Medicine.objects.create(name='Proc Med', unit='tablet', reorder_level=1, max_stock_level=50)
        received_po = PurchaseOrder.objects.create(
            supplier=supplier,
            ordered_by=self.staff,
            status='received',
            received_date=self.today,
        )
        PurchaseOrderItem.objects.create(
            purchase_order=received_po,
            medicine=med,
            quantity_ordered=6,
            unit_cost=Decimal('5.00'),
            quantity_received=6,
        )
        draft_po = PurchaseOrder.objects.create(
            supplier=supplier,
            ordered_by=self.staff,
            status='draft',
        )
        PurchaseOrderItem.objects.create(
            purchase_order=draft_po,
            medicine=med,
            quantity_ordered=99,
            unit_cost=Decimal('5.00'),
        )

        totals = procurement_totals_since(self.month_start)
        self.assertEqual(totals['total_qty'], 6)
        self.assertEqual(totals['total_cost'], Decimal('30.00'))

    def test_build_dashboard_context_includes_alert_counts(self):
        med = Medicine.objects.create(
            name='Low Stock Med',
            unit='tablet',
            reorder_level=10,
            max_stock_level=100,
            cached_non_expired_stock=3,
            stock_cache_updated_at=timezone.now(),
        )
        future = self.today + datetime.timedelta(days=400)
        Batch.objects.create(
            medicine=med,
            batch_number='LOW-1',
            quantity=3,
            expiry_date=future,
        )
        refresh_medicine_stock_cache(med.pk, self.today)

        ctx = build_dashboard_context(self.today)
        self.assertIn('low_stock_count', ctx)
        self.assertIn('near_expiry_count', ctx)
        self.assertGreaterEqual(ctx['low_stock_count'], 1)
        self.assertEqual(ctx['total_medicines'], Medicine.objects.filter(is_active=True).count())
