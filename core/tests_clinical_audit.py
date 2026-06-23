"""Tests for clinical PHI access audit trail."""

from datetime import date, time
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from appointments.models import Appointment
from core.clinical_audit import log_clinical_access
from core.models import ClinicalAccessLog
from dental_records.models import DentalRecord
from medical_records.models import MedicalRecord


User = get_user_model()


def _complete_staff_profile(user, staff_id='STAFF-001'):
    """Match medical_records.tests profile setup so middleware allows access."""
    user.first_name = user.first_name or 'Test'
    user.last_name = user.last_name or 'Staff'
    user.save(update_fields=['first_name', 'last_name'])
    profile = user.staff_profile
    if staff_id and not str(profile.staff_id).startswith('TEMP_'):
        profile.staff_id = staff_id
    elif staff_id:
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


class LogClinicalAccessTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.actor = User.objects.create_user(
            email='actor@test.com',
            password='pass',
            role='staff',
            first_name='Actor',
            last_name='User',
        )
        self.patient = User.objects.create_user(
            email='patient@test.com',
            password='pass',
            role='patient',
            first_name='Pat',
            last_name='Ient',
        )

    def test_log_clinical_access_creates_row(self):
        request = self.factory.get('/medical-records/1/')
        request.META['REMOTE_ADDR'] = '192.168.1.10'
        request.user = self.actor

        entry = log_clinical_access(
            request,
            action='view',
            resource_type='medical_record',
            resource_id=42,
            patient=self.patient,
            resource_label='Pat Ient — Jan 01, 2025',
        )

        self.assertIsNotNone(entry)
        self.assertEqual(ClinicalAccessLog.objects.count(), 1)
        log = ClinicalAccessLog.objects.get()
        self.assertEqual(log.actor, self.actor)
        self.assertEqual(log.patient, self.patient)
        self.assertEqual(log.action, 'view')
        self.assertEqual(log.resource_type, 'medical_record')
        self.assertEqual(log.resource_id, 42)
        self.assertEqual(log.ip_address, '192.168.1.10')
        self.assertEqual(log.request_path, '/medical-records/1/')

    def test_log_clinical_access_never_raises(self):
        request = self.factory.get('/test/')
        request.user = self.actor
        with patch('core.clinical_audit.ClinicalAccessLog.objects.create', side_effect=Exception('db down')):
            result = log_clinical_access(
                request,
                action='view',
                resource_type='medical_record',
                resource_id=1,
                patient=self.patient,
            )
        self.assertIsNone(result)


class MedicalRecordAuditIntegrationTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            email='med-staff@test.com',
            password='pass',
            role='staff',
            first_name='Med',
            last_name='Staff',
        )
        _complete_staff_profile(self.staff, 'MED-STAFF-1')
        self.other_staff = User.objects.create_user(
            email='other-staff@test.com',
            password='pass',
            role='staff',
            first_name='Other',
            last_name='Staff',
        )
        _complete_staff_profile(self.other_staff, 'MED-STAFF-2')
        self.patient = User.objects.create_user(
            email='med-patient@test.com',
            password='pass',
            role='patient',
            first_name='Med',
            last_name='Patient',
        )
        self.record = MedicalRecord.objects.create(
            patient=self.patient,
            doctor=self.staff,
            diagnosis='Test diagnosis',
            treatment='Test treatment',
        )
        self.client.force_login(self.staff)

    def test_view_medical_record_detail_creates_log(self):
        url = reverse('medical_records:medical_record_detail_page', args=[self.record.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        logs = ClinicalAccessLog.objects.filter(
            action='view',
            resource_type='medical_record',
            resource_id=self.record.id,
        )
        self.assertEqual(logs.count(), 1)
        self.assertEqual(logs.first().patient, self.patient)

    def test_denied_medical_record_view_creates_no_log(self):
        self.client.force_login(self.other_staff)
        url = reverse('medical_records:medical_record_detail_page', args=[self.record.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ClinicalAccessLog.objects.count(), 0)

    def test_create_medical_record_creates_log(self):
        appointment = Appointment.objects.create(
            patient=self.patient,
            doctor=self.staff,
            appointment_type='checkup',
            date=date.today(),
            time=time(10, 0),
            reason='Checkup',
            status='confirmed',
        )
        url = reverse('medical_records:create_medical_record', args=[appointment.id])
        response = self.client.post(url, {
            'diagnosis': 'New diagnosis',
            'treatment': 'New treatment',
            'lab_results': '',
        })
        self.assertEqual(response.status_code, 302)
        create_logs = ClinicalAccessLog.objects.filter(action='create', resource_type='medical_record')
        self.assertEqual(create_logs.count(), 1)
        self.assertEqual(create_logs.first().patient, self.patient)


class DentalRecordAuditIntegrationTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            email='den-staff@test.com',
            password='pass',
            role='staff',
            first_name='Den',
            last_name='Staff',
        )
        _complete_staff_profile(self.staff, 'DEN-STAFF-1')
        self.patient = User.objects.create_user(
            email='den-patient@test.com',
            password='pass',
            role='patient',
            first_name='Den',
            last_name='Patient',
        )
        self.record = DentalRecord.objects.create(
            patient=self.patient,
            gender='male',
            civil_status='single',
            address='123 Test St',
            date_of_birth=date(2000, 1, 1),
            place_of_birth='Test City',
            email=self.patient.email,
            contact_number='09171234567',
            designation='student',
            department_college_office='College',
            guardian_name='Guardian',
            guardian_contact='09179876543',
            examined_by=self.staff,
            status='completed',
            date_of_examination=date.today(),
        )
        self.client.force_login(self.staff)

    def test_view_dental_record_creates_log(self):
        url = reverse('dental_records:dental_record_detail', args=[self.record.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            ClinicalAccessLog.objects.filter(action='view', resource_type='dental_record').count(),
            1,
        )

    def test_edit_dental_record_creates_log(self):
        url = reverse('dental_records:dental_record_edit', args=[self.record.id])
        response = self.client.post(url, {
            'form_type': 'vital_signs',
            'blood_pressure': '120/80',
            'pulse_rate': '72',
            'respiratory_rate': '16',
            'temperature': '36.5',
            'weight': '70',
            'height': '170',
        })
        self.assertEqual(response.status_code, 302)
        edit_logs = ClinicalAccessLog.objects.filter(action='edit', resource_type='dental_record')
        self.assertEqual(edit_logs.count(), 1)
        self.assertEqual(edit_logs.first().metadata.get('section'), 'vital_signs')

    def test_delete_dental_record_retains_log(self):
        label = f'{self.patient.get_full_name()} — {self.record.date_of_examination.strftime("%b %d, %Y")}'
        url = reverse('dental_records:dental_record_delete', args=[self.record.id])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(DentalRecord.objects.filter(pk=self.record.id).exists())
        delete_logs = ClinicalAccessLog.objects.filter(action='delete', resource_type='dental_record')
        self.assertEqual(delete_logs.count(), 1)
        self.assertEqual(delete_logs.first().resource_label, label)
        self.assertIn('patient_name', delete_logs.first().metadata)

    def test_export_dental_record_creates_log(self):
        url = reverse('dental_records:dental_record_export_json', args=[self.record.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        export_logs = ClinicalAccessLog.objects.filter(action='export', resource_type='dental_record')
        self.assertEqual(export_logs.count(), 1)
        self.assertEqual(export_logs.first().metadata.get('format'), 'json')


class ClinicalAuditAccessControlTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email='admin-clinical@test.com',
            password='pass',
            role='admin',
            is_staff=True,
            first_name='Admin',
            last_name='User',
        )
        _complete_staff_profile(self.admin, 'ADM-CLIN-1')
        self.staff = User.objects.create_user(
            email='staff-clinical@test.com',
            password='pass',
            role='staff',
            first_name='Staff',
            last_name='User',
        )
        _complete_staff_profile(self.staff, 'STF-CLIN-1')
        self.patient = User.objects.create_user(
            email='audit-patient@test.com',
            password='pass',
            role='patient',
            first_name='Audit',
            last_name='Patient',
        )
        self.other_patient = User.objects.create_user(
            email='other-patient@test.com',
            password='pass',
            role='patient',
            first_name='Other',
            last_name='Patient',
        )
        ClinicalAccessLog.objects.create(
            actor=self.staff,
            patient=self.patient,
            action='view',
            resource_type='medical_record',
            resource_id=1,
            resource_label='Test',
        )
        ClinicalAccessLog.objects.create(
            actor=self.staff,
            patient=self.other_patient,
            action='view',
            resource_type='dental_record',
            resource_id=2,
            resource_label='Other',
        )

    def test_global_audit_page_forbidden_for_non_admin(self):
        self.client.force_login(self.staff)
        url = reverse('core:clinical_access_log')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('restricted', response.url)

    def test_global_audit_page_ok_for_admin(self):
        self.client.force_login(self.admin)
        url = reverse('core:clinical_access_log')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'core/clinical_access_log/list.html')
        self.assertEqual(len(response.context['logs']), 2)

    def test_global_audit_page_has_live_filter_form(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('core:clinical_access_log'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'clinical-access-log-filter-form')
        self.assertContains(response, 'clinical-access-log-results')
        self.assertContains(response, 'Results update as you type')
        self.assertNotContains(response, '>Filter</button>')

    def test_global_audit_htmx_returns_results_partial(self):
        self.client.force_login(self.admin)
        response = self.client.get(
            reverse('core:clinical_access_log'),
            {'action': 'view'},
            HTTP_HX_REQUEST='true',
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'core/clinical_access_log/_results.html')
        self.assertNotContains(response, 'clinical-access-log-filter-form')

    def test_global_audit_filters_by_action(self):
        self.client.force_login(self.admin)
        ClinicalAccessLog.objects.create(
            actor=self.staff,
            patient=self.patient,
            action='delete',
            resource_type='medical_record',
            resource_id=3,
            resource_label='Deleted record',
        )
        response = self.client.get(reverse('core:clinical_access_log'), {'action': 'delete'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['logs']), 1)
        self.assertEqual(response.context['logs'][0].action, 'delete')

    def test_patient_audit_page_filters_by_patient(self):
        self.client.force_login(self.admin)
        url = reverse('core:patient_clinical_access_log', kwargs={'user_id': self.patient.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['logs']), 1)
        self.assertEqual(response.context['logs'][0].patient, self.patient)
