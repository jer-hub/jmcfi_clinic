"""HTMX partial and API response tests (Pharmacy Phase 5)."""

import datetime
import json

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from pharmacy.models import Batch, Medicine
from pharmacy.test_helpers import make_user, pharmacy_test_settings


@pharmacy_test_settings
class PharmacyHtmxListTest(TestCase):
    def setUp(self):
        self.staff = make_user(role='staff', email='htmx-staff@test.example')
        self.client.force_login(self.staff)
        self.htmx_headers = {'HTTP_HX_REQUEST': 'true'}

    def test_medicine_list_htmx_returns_table_oob_fragment(self):
        Medicine.objects.create(name='HTMX Med', unit='tablet', reorder_level=1, max_stock_level=50)
        response = self.client.get(reverse('pharmacy:medicine_list'), **self.htmx_headers)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="jmcfi-pharm-medicine-list-table"')
        self.assertContains(response, 'hx-swap-oob="true"')
        self.assertContains(response, 'HTMX Med')

    def test_batch_list_htmx_returns_table_oob_fragment(self):
        med = Medicine.objects.create(name='Batch HTMX', unit='tablet', reorder_level=1, max_stock_level=50)
        future = timezone.now().date() + datetime.timedelta(days=300)
        Batch.objects.create(medicine=med, batch_number='B-HTMX', quantity=5, expiry_date=future)
        response = self.client.get(reverse('pharmacy:batch_list'), **self.htmx_headers)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="jmcfi-pharm-batch-list-table"')
        self.assertContains(response, 'B-HTMX')

    def test_purchase_order_list_htmx_returns_table_oob_fragment(self):
        response = self.client.get(reverse('pharmacy:purchase_order_list'), **self.htmx_headers)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="jmcfi-pharm-po-list-table"')
        self.assertContains(response, 'hx-swap-oob="true"')


@pharmacy_test_settings
class PharmacyBatchApiTest(TestCase):
    def setUp(self):
        self.staff = make_user(role='staff', email='htmx-api-staff@test.example')
        self.client.force_login(self.staff)
        self.medicine = Medicine.objects.create(
            name='API Med',
            unit='tablet',
            reorder_level=1,
            max_stock_level=50,
        )
        future = timezone.now().date() + datetime.timedelta(days=200)
        self.batch = Batch.objects.create(
            medicine=self.medicine,
            batch_number='API-B1',
            quantity=12,
            expiry_date=future,
        )
        self.url = reverse(
            'pharmacy:api_batches_for_medicine',
            kwargs={'medicine_id': self.medicine.pk},
        )

    def test_htmx_request_returns_option_markup(self):
        response = self.client.get(self.url, HTTP_HX_REQUEST='true')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<option')
        self.assertContains(response, 'API-B1')
        self.assertNotContains(response, 'application/json')

    def test_json_request_returns_batch_payload(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['batch_number'], 'API-B1')
        self.assertEqual(data[0]['quantity'], 12)

    def test_student_cannot_access_batch_api(self):
        student = make_user(role='student', email='htmx-api-student@test.example')
        self.client.force_login(student)
        response = self.client.get(self.url)
        self.assertIn(response.status_code, (302, 403))

    def test_htmx_batch_options_mark_fefo_recommended(self):
        response = self.client.get(self.url, HTTP_HX_REQUEST='true')
        self.assertContains(response, 'recommended')
        self.assertContains(response, 'Select a batch')


@pharmacy_test_settings
class PharmacyMedicineApiTest(TestCase):
    def setUp(self):
        self.staff = make_user(role='staff', email='htmx-med-staff@test.example')
        self.client.force_login(self.staff)
        self.medicine = Medicine.objects.create(
            name='Meta Med',
            unit='tablet',
            strength='500mg',
            requires_prescription=True,
            reorder_level=1,
            max_stock_level=50,
            cached_non_expired_stock=20,
            stock_cache_updated_at=timezone.now(),
        )
        self.url = reverse(
            'pharmacy:api_medicine_detail',
            kwargs={'medicine_id': self.medicine.pk},
        )

    def test_medicine_detail_returns_metadata_json(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data['name'], 'Meta Med (500mg)')
        self.assertEqual(data['unit'], 'tablet')
        self.assertTrue(data['requires_prescription'])
        self.assertEqual(data['current_stock'], 20)

    def test_student_cannot_access_medicine_api(self):
        student = make_user(role='student', email='htmx-med-student@test.example')
        self.client.force_login(student)
        response = self.client.get(self.url)
        self.assertIn(response.status_code, (302, 403))
