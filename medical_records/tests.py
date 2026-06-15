from datetime import date, time, timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
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


@override_settings(
	MIDDLEWARE=[
		middleware
		for middleware in settings.MIDDLEWARE
		if middleware != 'core.middleware.ProfileCompleteMiddleware'
	]
)
class StaffMedicalRecordsReadOnlyTests(TestCase):
	def setUp(self):
		self.staff = User.objects.create_user(
			email='staff-readonly@example.com',
			password='test-pass-123',
			role='staff',
			first_name='Staff',
			last_name='Viewer',
		)
		self.doctor = User.objects.create_user(
			email='doctor-readonly@example.com',
			password='test-pass-123',
			role='doctor',
			first_name='Doc',
			last_name='Tor',
		)
		self.patient = User.objects.create_user(
			email='patient-readonly@example.com',
			password='test-pass-123',
			role='patient',
			first_name='Pat',
			last_name='Ient',
		)
		self.staff.staff_profile.department = 'Clinic'
		self.staff.staff_profile.phone = '09123456789'
		self.staff.staff_profile.save(update_fields=['department', 'phone'])
		self.doctor.staff_profile.license_number = 'LIC-1'
		self.doctor.staff_profile.ptr_no = 'PTR-1'
		self.doctor.staff_profile.phone = '09998887777'
		self.doctor.staff_profile.save(update_fields=['license_number', 'ptr_no', 'phone'])

		self.record = MedicalRecord.objects.create(
			patient=self.patient,
			doctor=self.doctor,
			diagnosis='Test diagnosis',
			treatment='Rest',
		)

	def test_staff_can_view_clinic_wide_medical_list(self):
		self.client.force_login(self.staff)
		response = self.client.get(reverse('medical_records:medical_records'))
		self.assertEqual(response.status_code, 200)
		self.assertGreaterEqual(response.context['total_count'], 1)

	def test_staff_can_view_any_medical_record_detail(self):
		self.client.force_login(self.staff)
		response = self.client.get(
			reverse('medical_records:medical_record_detail_page', args=[self.record.id])
		)
		self.assertEqual(response.status_code, 200)

	def test_staff_cannot_create_medical_record_for_patient(self):
		self.client.force_login(self.staff)
		response = self.client.get(reverse('medical_records:create_medical_record_for_patient'))
		self.assertEqual(response.status_code, 302)
