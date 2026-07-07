from datetime import date, time, timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from appointments.models import Appointment
from dental_records.models import DentalRecord
from core.tests import _complete_staff_like_profile, _complete_student_profile


User = get_user_model()


class DentalRecordsListTotalsTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            email='dr-staff@example.com',
            password='test-pass-123',
            role='staff',
            first_name='Staff',
            last_name='User',
        )
        self.student = User.objects.create_user(
            email='dr-student@example.com',
            password='test-pass-123',
            role='patient',
            first_name='Student',
            last_name='One',
        )
        _complete_staff_like_profile(self.staff, 'ST-2000')
        _complete_student_profile(self.student, 'S-2000')

    def _create_dental_appointment(self, status, appt_date, hour, appointment_type='dental'):
        return Appointment.objects.create(
            patient=self.student,
            doctor=self.staff,
            appointment_type=appointment_type,
            date=appt_date,
            time=time(hour, 0),
            reason=f'{status} reason',
            status=status,
        )

    def _create_dental_record(self, *, status='pending', appointment=None):
        return DentalRecord.objects.create(
            patient=self.student,
            gender='male',
            civil_status='single',
            address='123 Test St',
            date_of_birth=date(2000, 1, 1),
            place_of_birth='Test City',
            email=self.student.email,
            contact_number='09171234567',
            designation='student',
            department_college_office='College of Test',
            guardian_name='Guardian',
            guardian_contact='09179876543',
            examined_by=self.staff,
            appointment=appointment,
            status=status,
        )

    def test_badge_totals_match_mixed_timeline_rows(self):
        completed_appt = self._create_dental_appointment('completed', date.today(), 9)
        future_day = date.today() + timedelta(days=7)
        self._create_dental_appointment('pending', future_day, 12)
        self._create_dental_appointment(
            'pending',
            date.today() - timedelta(days=2),
            14,
        )

        self._create_dental_record(status='completed', appointment=completed_appt)
        self._create_dental_record(status='pending')

        self.client.force_login(self.staff)
        response = self.client.get(reverse('dental_records:dental_record_list'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context['status_totals'],
            {
                'pending': 2,
                'missed': 1,
                'completed': 1,
                'cancelled': 0,
            },
        )
        self.assertEqual(response.context['total_count'], 4)

    def test_status_filter_pending_updates_total_count(self):
        future_day = date.today() + timedelta(days=7)
        self._create_dental_appointment('pending', future_day, 10)
        self._create_dental_record(status='completed')

        self.client.force_login(self.staff)
        response = self.client.get(
            reverse('dental_records:dental_record_list'),
            {'status': 'pending'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_count'], 1)

    def test_htmx_filter_response_includes_header_total_oob(self):
        future_day = date.today() + timedelta(days=7)
        self._create_dental_appointment('pending', future_day, 11)

        self.client.force_login(self.staff)
        response = self.client.get(
            reverse('dental_records:dental_record_list'),
            HTTP_HX_REQUEST='true',
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'jmcfi-dr-header-total-count')
        self.assertContains(response, 'hx-swap-oob="true"')

    def test_cancelled_appointment_totals_and_status_filter(self):
        future_day = date.today() + timedelta(days=7)
        self._create_dental_appointment('pending', future_day, 9)
        self._create_dental_appointment('cancelled', future_day, 15)

        self.client.force_login(self.staff)
        response = self.client.get(reverse('dental_records:dental_record_list'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['status_totals']['cancelled'], 1)

        filtered = self.client.get(
            reverse('dental_records:dental_record_list'),
            {'status': 'cancelled'},
        )
        self.assertEqual(filtered.context['total_count'], 1)


@override_settings(
    MIDDLEWARE=[
        middleware
        for middleware in settings.MIDDLEWARE
        if middleware != 'core.middleware.ProfileCompleteMiddleware'
    ]
)
class StaffDentalRecordsReadOnlyTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            email='staff-dr-readonly@example.com',
            password='test-pass-123',
            role='staff',
            first_name='Staff',
            last_name='Viewer',
        )
        self.patient = User.objects.create_user(
            email='patient-dr-readonly@example.com',
            password='test-pass-123',
            role='patient',
            first_name='Pat',
            last_name='Ient',
        )
        self.staff.staff_profile.department = 'Clinic'
        self.staff.staff_profile.phone = '09123456789'
        self.staff.staff_profile.save(update_fields=['department', 'phone'])

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
            department_college_office='College of Test',
            guardian_name='Guardian',
            guardian_contact='09179876543',
            status='completed',
        )

    def test_staff_can_view_dental_list_and_detail(self):
        self.client.force_login(self.staff)
        list_response = self.client.get(reverse('dental_records:dental_record_list'))
        self.assertEqual(list_response.status_code, 200)

        detail_response = self.client.get(
            reverse('dental_records:dental_record_detail', args=[self.record.id])
        )
        self.assertEqual(detail_response.status_code, 200)

    def test_staff_cannot_create_dental_record(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse('dental_records:dental_record_create'))
        self.assertEqual(response.status_code, 302)

    def test_staff_cannot_edit_dental_record(self):
        self.client.force_login(self.staff)
        response = self.client.get(
            reverse('dental_records:dental_record_edit', args=[self.record.id])
        )
        self.assertEqual(response.status_code, 302)


@override_settings(
    MIDDLEWARE=[
        middleware
        for middleware in settings.MIDDLEWARE
        if middleware != 'core.middleware.ProfileCompleteMiddleware'
    ]
)
class DentalRecordEditSaveTests(TestCase):
    def setUp(self):
        self.doctor = User.objects.create_user(
            email='doctor-dr-edit@example.com',
            password='test-pass-123',
            role='doctor',
            first_name='Doc',
            last_name='Tor',
        )
        self.patient = User.objects.create_user(
            email='patient-dr-edit@example.com',
            password='test-pass-123',
            role='patient',
            first_name='Pat',
            last_name='Edit',
        )
        self.doctor.staff_profile.department = 'Clinic'
        self.doctor.staff_profile.phone = '09123456789'
        self.doctor.staff_profile.save(update_fields=['department', 'phone'])

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
            department_college_office='College of Test',
            guardian_name='Guardian',
            guardian_contact='09179876543',
            examined_by=self.doctor,
            status='completed',
        )
        self.edit_url = reverse('dental_records:dental_record_edit', args=[self.record.id])

    def test_edit_page_includes_section_save_attributes(self):
        self.client.force_login(self.doctor)
        response = self.client.get(self.edit_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-section-save="ajax"')
        self.assertContains(response, 'data-section="demographics"')
        self.assertContains(response, 'Back to Details')
        self.assertContains(response, 'rounded-card')
        self.assertContains(response, 'aria-label="Dental record sections"')
        self.assertContains(response, 'Edit')
        self.assertContains(response, 'unsaved-changes-modal')

    def test_ajax_demographics_save_returns_json(self):
        self.client.force_login(self.doctor)
        response = self.client.post(
            self.edit_url,
            {
                'form_type': 'demographics',
                'patient': self.patient.id,
                'middle_name': 'Updated',
                'age': '26',
                'gender': 'male',
                'civil_status': 'single',
                'date_of_birth': '2000-01-01',
                'place_of_birth': 'Test City',
                'address': '123 Test St',
                'email': self.patient.email,
                'contact_number': '9171234567',
                'designation': 'student',
                'department_college_office': 'College of Test',
                'guardian_name': 'Guardian',
                'guardian_contact': '9179876543',
                'examined_by': self.doctor.id,
                'date_of_examination': '2026-07-05',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['section'], 'demographics')
        self.record.refresh_from_db()
        self.assertEqual(self.record.middle_name, 'Updated')

    def test_ajax_invalid_section_save_returns_field_errors(self):
        self.client.force_login(self.doctor)
        response = self.client.post(
            self.edit_url,
            {
                'form_type': 'demographics',
                'patient': self.patient.id,
                'middle_name': 'Updated',
                'age': '26',
                'gender': 'male',
                'civil_status': 'single',
                'date_of_birth': '2000-01-01',
                'place_of_birth': 'Test City',
                'address': '123 Test St',
                'email': self.patient.email,
                'contact_number': '9171234567',
                'designation': 'student',
                'department_college_office': 'College of Test',
                'guardian_name': 'Guardian',
                'guardian_contact': '9179876543',
                'examined_by': self.doctor.id,
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data['success'])
        self.assertIn('errors', data)
