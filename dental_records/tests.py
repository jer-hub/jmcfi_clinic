from datetime import date, time, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from appointments.models import Appointment
from dental_records.models import DentalRecord


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
            role='student',
            first_name='Student',
            last_name='One',
        )
        self.staff.staff_profile.department = 'Clinic'
        self.staff.staff_profile.phone = '09123456789'
        self.staff.staff_profile.save(update_fields=['department', 'phone'])

    def _create_dental_appointment(self, status, appt_date, hour, appointment_type='dental'):
        return Appointment.objects.create(
            student=self.student,
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
