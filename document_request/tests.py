from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.test.utils import override_settings
from django.conf import settings

from core.models import StaffProfile, StudentProfile, User
from document_request.models import DocumentRequest, StudentRequestSchedule


@override_settings(
	MIDDLEWARE=[
		middleware
		for middleware in settings.MIDDLEWARE
		if middleware != 'core.middleware.ProfileCompleteMiddleware'
	]
)
class DocumentRequestFlowTests(TestCase):
	def setUp(self):
		self.student = User.objects.create_user(
			email='student@example.com',
			password='pass1234',
			role='student',
			first_name='Test',
			last_name='Student',
		)
		student_profile, _ = StudentProfile.objects.get_or_create(user=self.student)
		student_profile.student_id = 'S-1001'
		student_profile.date_of_birth = '2004-01-01'
		student_profile.phone = '09123456789'
		student_profile.emergency_contact = 'Parent'
		student_profile.emergency_phone = '09999999999'
		student_profile.blood_type = 'O+'
		student_profile.save()

		self.doctor = User.objects.create_user(
			email='doctor@example.com',
			password='pass1234',
			role='doctor',
			first_name='Doc',
			last_name='Tor',
			is_staff=True,
		)
		staff_profile, _ = StaffProfile.objects.get_or_create(user=self.doctor)
		staff_profile.staff_id = 'D-2001'
		staff_profile.department = 'Health Services'
		staff_profile.phone = '09112223333'
		staff_profile.license_number = 'LIC-001'
		staff_profile.ptr_no = 'PTR-001'
		staff_profile.save()

	def test_student_medical_record_request_requires_active_schedule(self):
		self.client.force_login(self.student)

		response = self.client.post(
			reverse('document_request:request_document'),
			{'document_type': 'medical_record', 'purpose': 'Employment requirement'},
			follow=True,
		)

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.request['PATH_INFO'], reverse('document_request:request_document'))
		self.assertFalse(
			DocumentRequest.objects.filter(
				student=self.student,
				document_type='medical_record',
			).exists()
		)

	def test_student_medical_record_request_succeeds_inside_schedule(self):
		now = timezone.localtime()
		day_code = StudentRequestSchedule.WEEKDAY_TO_CODE[now.weekday()]
		StudentRequestSchedule.objects.create(
			student=self.student,
			allowed_days=[day_code],
			start_time='00:00',
			end_time='23:59',
			is_active=True,
			updated_by=self.doctor,
		)

		self.client.force_login(self.student)
		response = self.client.post(
			reverse('document_request:request_document'),
			{'document_type': 'medical_record', 'purpose': 'Scholarship requirement'},
			follow=True,
		)

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.request['PATH_INFO'], reverse('document_request:document_requests'))
		created = DocumentRequest.objects.filter(
			student=self.student,
			document_type='medical_record',
		).first()
		self.assertIsNotNone(created)
		self.assertEqual(created.request_origin, 'student')
		self.assertEqual(created.created_by, self.student)
