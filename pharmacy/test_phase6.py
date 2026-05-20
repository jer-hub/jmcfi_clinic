"""Phase 6: stock cache, alerts command, analytics integration."""

import datetime
from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from pharmacy.models import Batch, Medicine
from pharmacy.services.alerts import run_inventory_alerts
from pharmacy.services.stock_snapshot import (
    compute_non_expired_stock,
    refresh_all_medicine_stock_caches,
    refresh_medicine_stock_cache,
)
from pharmacy.test_helpers import make_user


class StockSnapshotTest(TestCase):
    def setUp(self):
        self.medicine = Medicine.objects.create(
            name='Cache Med',
            unit='tablet',
            reorder_level=5,
            max_stock_level=100,
        )
        future = timezone.now().date() + datetime.timedelta(days=200)
        past = timezone.now().date() - datetime.timedelta(days=1)
        Batch.objects.create(
            medicine=self.medicine,
            batch_number='C-OK',
            quantity=10,
            expiry_date=future,
        )
        Batch.objects.create(
            medicine=self.medicine,
            batch_number='C-EXP',
            quantity=99,
            expiry_date=past,
        )

    def test_compute_excludes_expired_batches(self):
        self.assertEqual(compute_non_expired_stock(self.medicine.pk), 10)

    def test_refresh_updates_cached_fields(self):
        refresh_medicine_stock_cache(self.medicine.pk)
        self.medicine.refresh_from_db()
        self.assertEqual(self.medicine.cached_non_expired_stock, 10)
        self.assertIsNotNone(self.medicine.stock_cache_updated_at)
        self.assertEqual(self.medicine.current_stock, 10)

    def test_batch_save_refreshes_cache_via_signal(self):
        future = timezone.now().date() + datetime.timedelta(days=300)
        Batch.objects.create(
            medicine=self.medicine,
            batch_number='C-NEW',
            quantity=4,
            expiry_date=future,
        )
        self.medicine.refresh_from_db()
        self.assertEqual(self.medicine.cached_non_expired_stock, 14)


class InventoryAlertsTest(TestCase):
    def setUp(self):
        self.staff = make_user(role='staff', email='alert-staff@test.example')
        self.medicine = Medicine.objects.create(
            name='Alert Med',
            unit='tablet',
            reorder_level=20,
            max_stock_level=100,
            cached_non_expired_stock=3,
            stock_cache_updated_at=timezone.now(),
        )

    def test_dry_run_reports_without_notifications(self):
        stats = run_inventory_alerts(dry_run=True)
        self.assertTrue(stats['dry_run'])
        self.assertGreaterEqual(stats['low_stock_medicines'], 1)
        self.assertEqual(stats['notifications_sent'], 0)

    def test_alerts_notify_staff_when_not_dry_run(self):
        from core.models import Notification

        stats = run_inventory_alerts(dry_run=False)
        self.assertGreater(stats['notifications_sent'], 0)
        self.assertTrue(
            Notification.objects.filter(user=self.staff, title__startswith='Pharmacy:').exists()
        )


class PharmacyInventoryAlertsCommandTest(TestCase):
    def test_command_runs_dry_run(self):
        make_user(role='staff', email='cmd-staff@test.example')
        Medicine.objects.create(
            name='Cmd Med',
            unit='tablet',
            reorder_level=10,
            max_stock_level=50,
        )
        out = StringIO()
        call_command('pharmacy_inventory_alerts', '--dry-run', stdout=out)
        self.assertIn('DRY RUN', out.getvalue())


class PharmacyAnalyticsSummaryTest(TestCase):
    def test_build_pharmacy_analytics_summary_returns_expected_keys(self):
        from pharmacy.services.reports import build_pharmacy_analytics_summary

        today = timezone.now().date()
        summary = build_pharmacy_analytics_summary(
            today - datetime.timedelta(days=30),
            today,
        )
        self.assertIn('active_medicines', summary)
        self.assertIn('low_stock_count', summary)
        self.assertIn('inventory_value', summary)
        self.assertIn('period_dispensed_cost', summary)
