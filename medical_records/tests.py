from datetime import date, time, timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from appointments.models import Appointment
from medical_records.models import MedicalRecord
from core.tests import _complete_staff_like_profile, _complete_student_profile


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

		_complete_staff_like_profile(self.staff, 'ST-1000')
		_complete_student_profile(self.student, 'S-1000')

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


@override_settings(
	MIDDLEWARE=[
		middleware
		for middleware in settings.MIDDLEWARE
		if middleware != 'core.middleware.ProfileCompleteMiddleware'
	]
)
class MedicalRecordDateTests(TestCase):
	def setUp(self):
		self.doctor = User.objects.create_user(
			email='doctor-record-date@example.com',
			password='test-pass-123',
			role='doctor',
			first_name='Doc',
			last_name='Tor',
		)
		self.patient = User.objects.create_user(
			email='patient-record-date@example.com',
			password='test-pass-123',
			role='patient',
			first_name='Pat',
			last_name='Ient',
		)
		self.doctor.staff_profile.license_number = 'LIC-2'
		self.doctor.staff_profile.ptr_no = 'PTR-2'
		self.doctor.staff_profile.phone = '09998887766'
		self.doctor.staff_profile.department = 'Clinic'
		self.doctor.staff_profile.specialization = 'General Medicine'
		self.doctor.staff_profile.save(update_fields=['license_number', 'ptr_no', 'phone', 'department', 'specialization'])
		self.patient.patient_profile.patient_id = 'P-REC-001'
		self.patient.patient_profile.course = 'BS IT'
		self.patient.patient_profile.department = 'CITE'
		self.patient.patient_profile.save(update_fields=['patient_id', 'course', 'department'])

	def test_record_date_defaults_from_appointment(self):
		appointment = Appointment.objects.create(
			patient=self.patient,
			doctor=self.doctor,
			appointment_type='checkup',
			date=date(2026, 3, 10),
			time=time(10, 0),
			reason='Checkup',
			status='completed',
		)
		record = MedicalRecord.objects.create(
			patient=self.patient,
			doctor=self.doctor,
			appointment=appointment,
			diagnosis='Test',
			treatment='Rest',
		)
		self.assertEqual(record.record_date, date(2026, 3, 10))

	def test_visit_snapshot_frozen_at_creation(self):
		record = MedicalRecord.objects.create(
			patient=self.patient,
			doctor=self.doctor,
			diagnosis='Test',
			treatment='Rest',
		)
		self.assertEqual(record.display_patient_name, 'Pat Ient')
		self.assertEqual(record.display_patient_id, 'P-REC-001')
		self.assertEqual(record.display_patient_course, 'BS IT')
		self.assertEqual(record.display_doctor_department, 'Clinic')

		self.patient.first_name = 'Changed'
		self.patient.save(update_fields=['first_name'])
		self.patient.patient_profile.course = 'BS CS'
		self.patient.patient_profile.save(update_fields=['course'])

		record.refresh_from_db()
		self.assertEqual(record.display_patient_name, 'Pat Ient')
		self.assertEqual(record.display_patient_course, 'BS IT')
