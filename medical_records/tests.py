from datetime import date, time, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from appointments.models import Appointment
from medical_records.models import MedicalRecord


User = get_user_model()


class MedicalRecordsBadgeCountTests(TestCase):
	def setUp(self):
		self.staff = User.objects.create_user(
			email='staff@example.com',
			password='test-pass-123',
			role='staff',
			first_name='Staff',
			last_name='User',
		)
		self.student = User.objects.create_user(
			email='student@example.com',
			password='test-pass-123',
			role='patient',
			first_name='Student',
			last_name='One',
		)

		# Satisfy ProfileCompleteMiddleware requirements for staff access.
		self.staff.staff_profile.department = 'Clinic'
		self.staff.staff_profile.phone = '09123456789'
		self.staff.staff_profile.save(update_fields=['department', 'phone'])

	def _create_appointment(self, status, hour, appointment_type='checkup', *, appt_date=None):
		return Appointment.objects.create(
			patient=self.student,
			doctor=self.staff,
			appointment_type=appointment_type,
			date=appt_date or date.today(),
			time=time(hour, 0),
			reason=f'{status} reason',
			status=status,
		)

	def test_badge_totals_match_mixed_timeline_rows(self):
		completed_with_record = self._create_appointment('completed', 9)
		self._create_appointment('confirmed', 10)
		self._create_appointment('cancelled', 11)
		self._create_appointment('pending', 9, appt_date=date.today() + timedelta(days=1))
		self._create_appointment('completed', 13)

		MedicalRecord.objects.create(
			patient=self.student,
			doctor=self.staff,
			appointment=completed_with_record,
			diagnosis='Recovered',
			treatment='Routine check',
		)
		MedicalRecord.objects.create(
			patient=self.student,
			doctor=self.staff,
			diagnosis='Observation',
			treatment='Monitor symptoms',
		)

		self.client.force_login(self.staff)
		response = self.client.get(reverse('medical_records:medical_records'))

		self.assertEqual(response.status_code, 200)
		self.assertEqual(
			response.context['status_totals'],
			{
				'completed': 3,
				'confirmed': 1,
				'cancelled': 1,
				'pending': 1,
				'missed': 0,
			},
		)
		self.assertEqual(response.context['total_count'], 6)
