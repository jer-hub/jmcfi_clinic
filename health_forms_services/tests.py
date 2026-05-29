from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse

from core.models import PatientProfile, StaffProfile, User
from health_forms_services.models import (
	DentalHealthForm,
	DentalServicesRequest,
	HealthProfileForm,
	PatientChart,
	Prescription,
)


def _complete_staff_like_profile(user, staff_id, department='Clinic Operations'):
	profile, _ = StaffProfile.objects.get_or_create(user=user)
	profile.staff_id = staff_id
	profile.department = department
	profile.phone = '09123456789'
	profile.save()
	return profile


@override_settings(
	MIDDLEWARE=[
		middleware
		for middleware in settings.MIDDLEWARE
		if middleware != 'core.middleware.ProfileCompleteMiddleware'
	]
)
class HealthFormsAdminAccessTests(TestCase):
	def setUp(self):
		self.admin_user = User.objects.create_user(
			email='admin-health@test.com',
			password='AdminPass123!',
			role='admin',
			is_staff=True,
			is_active=True,
		)
		self.admin_user.first_name = 'Admin'
		self.admin_user.last_name = 'User'
		self.admin_user.save(update_fields=['first_name', 'last_name'])
		_complete_staff_like_profile(self.admin_user, 'ADM-HF-001')
		self.client.force_login(self.admin_user)

	def test_admin_is_redirected_from_health_forms_list(self):
		response = self.client.get(reverse('health_forms_services:forms_list'))
		self.assertRedirects(
			response,
			reverse('core:restricted_access')
			+ '?reason=clinical_admin_blocked&next=%2Fhealth-forms%2F',
		)


@override_settings(
	MIDDLEWARE=[
		middleware
		for middleware in settings.MIDDLEWARE
		if middleware != 'core.middleware.ProfileCompleteMiddleware'
	]
)
class HealthFormsPatientPickerTests(TestCase):
	def setUp(self):
		self.doctor = User.objects.create_user(
			email='doctor-picker@test.com',
			password='DoctorPass123!',
			role='doctor',
			is_staff=True,
			is_active=True,
			first_name='Picker',
			last_name='Doctor',
		)
		_complete_staff_like_profile(self.doctor, 'DOC-HF-001')

		self.patient = User.objects.create_user(
			email='patient-picker@test.com',
			password='PatientPass123!',
			role='patient',
			is_active=True,
			first_name='Ana',
			last_name='Patient',
		)
		PatientProfile.objects.update_or_create(
			user=self.patient,
			defaults={
				'patient_id': 'P-1001',
				'middle_name': 'M',
				'gender': 'female',
				'civil_status': 'single',
				'address': '123 Main St',
				'phone': '09171234567',
				'telephone_number': '0281234567',
				'emergency_contact': 'Parent Name',
				'emergency_phone': '09179876543',
				'course': 'BSN',
				'department': 'College of Nursing',
				'age': 21,
			},
		)

		self.other_patient = User.objects.create_user(
			email='other-picker@test.com',
			password='PatientPass123!',
			role='patient',
			is_active=True,
			first_name='Ben',
			last_name='Other',
		)
		PatientProfile.objects.update_or_create(
			user=self.other_patient,
			defaults={'patient_id': 'P-1002'},
		)

		self.client.force_login(self.doctor)

	def test_search_patients_returns_picker_payload(self):
		response = self.client.get(
			reverse('health_forms_services:search_patients'),
			{'q': 'Ana'},
		)
		self.assertEqual(response.status_code, 200)
		payload = response.json()
		self.assertIn('results', payload)
		self.assertTrue(payload['results'])
		first = payload['results'][0]
		self.assertIn('id', first)
		self.assertIn('name', first)
		self.assertIn('patient_id', first)
		self.assertEqual(first['id'], self.patient.id)

	def test_patient_profile_prefill_endpoint_returns_expected_fields(self):
		response = self.client.get(
			reverse('health_forms_services:patient_profile_prefill', args=[self.patient.id]),
		)
		self.assertEqual(response.status_code, 200)
		payload = response.json()
		self.assertEqual(payload['first_name'], 'Ana')
		self.assertEqual(payload['last_name'], 'Patient')
		self.assertEqual(payload['contact_number'], '09171234567')
		self.assertEqual(payload['department_college_office'], 'BSN - College of Nursing')
		self.assertEqual(payload['guardian_name'], 'Parent Name')

	def test_create_patient_chart_uses_selected_patient_user(self):
		response = self.client.post(
			reverse('health_forms_services:create_patient_chart'),
			{
				'selected_user_id': str(self.patient.id),
				'last_name': 'Patient',
				'first_name': 'Ana',
				'middle_name': 'M',
				'address': '123 Main St',
				'date_of_birth': '',
				'place_of_birth': '',
				'age': '21',
				'gender': 'female',
				'civil_status': 'single',
				'email_address': 'patient-picker@test.com',
				'contact_number': '09171234567',
				'telephone_number': '0281234567',
				'designation': 'student',
				'department_college_office': 'BSN - College of Nursing',
				'guardian_name': 'Parent Name',
				'guardian_contact': '+639179876543',
			},
			follow=True,
		)
		self.assertEqual(response.status_code, 200)
		created = PatientChart.objects.latest('created_at')
		self.assertEqual(created.user_id, self.patient.id)

	def test_create_dental_services_uses_selected_patient_user(self):
		response = self.client.post(
			reverse('health_forms_services:create_dental_services'),
			{
				'selected_user_id': str(self.patient.id),
				'last_name': 'Patient',
				'first_name': 'Ana',
				'middle_name': 'M',
				'address': '123 Main St',
				'age': '21',
				'gender': 'female',
				'date_of_birth': '',
				'contact_number': '09171234567',
				'department': 'BSN - College of Nursing',
			},
			follow=True,
		)
		self.assertEqual(response.status_code, 200)
		created = DentalServicesRequest.objects.latest('created_at')
		self.assertEqual(created.user_id, self.patient.id)

	def test_create_dental_form_uses_selected_patient_user(self):
		response = self.client.post(
			reverse('health_forms_services:create_dental_form'),
			{
				'selected_user_id': str(self.patient.id),
				'last_name': 'Patient',
				'first_name': 'Ana',
				'middle_name': 'M',
				'age': '21',
				'gender': 'female',
				'civil_status': 'single',
				'address': '123 Main St',
				'date_of_birth': '',
				'place_of_birth': '',
				'email_address': 'patient-picker@test.com',
				'contact_number': '09171234567',
				'telephone_number': '0281234567',
				'designation': 'student',
				'department_college_office': 'BSN - College of Nursing',
				'guardian_name': 'Parent Name',
				'guardian_contact': '+639179876543',
				'date_of_examination': '',
			},
			follow=True,
		)
		self.assertEqual(response.status_code, 200)
		created = DentalHealthForm.objects.latest('created_at')
		self.assertEqual(created.user_id, self.patient.id)

	def test_invalid_selected_user_is_rejected(self):
		response = self.client.post(
			reverse('health_forms_services:create_dental_services'),
			{
				'selected_user_id': '999999',
				'last_name': 'Doctor',
				'first_name': 'Picker',
				'middle_name': '',
				'address': '',
				'age': '',
				'gender': '',
				'date_of_birth': '',
				'contact_number': '',
				'department': '',
			},
		)
		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Please select a valid patient from the search results.')
		self.assertFalse(DentalServicesRequest.objects.exists())

	def test_invalid_selected_user_is_rejected_for_dental_form(self):
		response = self.client.post(
			reverse('health_forms_services:create_dental_form'),
			{
				'selected_user_id': '999999',
				'last_name': 'Doctor',
				'first_name': 'Picker',
				'middle_name': '',
				'age': '',
				'gender': '',
				'civil_status': '',
				'address': '',
				'date_of_birth': '',
				'place_of_birth': '',
				'email_address': '',
				'contact_number': '',
				'telephone_number': '',
				'designation': '',
				'department_college_office': '',
				'guardian_name': '',
				'guardian_contact': '',
				'date_of_examination': '',
			},
		)
		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Please select a valid patient from the search results.')
		self.assertFalse(DentalHealthForm.objects.exists())

	def test_no_selected_user_keeps_creator_assignment(self):
		self.client.post(
			reverse('health_forms_services:create_patient_chart'),
			{
				'last_name': 'Doctor',
				'first_name': 'Picker',
				'middle_name': '',
				'address': '',
				'date_of_birth': '',
				'place_of_birth': '',
				'age': '',
				'gender': '',
				'civil_status': '',
				'email_address': '',
				'contact_number': '',
				'telephone_number': '',
				'designation': '',
				'department_college_office': '',
				'guardian_name': '',
				'guardian_contact': '',
			},
		)
		created = PatientChart.objects.latest('created_at')
		self.assertEqual(created.user_id, self.doctor.id)

	def test_create_health_profile_uses_selected_patient_user(self):
		response = self.client.post(
			reverse('health_forms_services:manual_entry'),
			{
				'selected_user_id': str(self.patient.id),
				'last_name': 'Patient',
				'first_name': 'Ana',
				'middle_name': 'M',
				'permanent_address': '123 Main St',
				'zip_code': '',
				'current_address': '123 Main St',
				'religion': '',
				'civil_status': 'single',
				'place_of_birth': 'Manila',
				'date_of_birth': '2000-01-15',
				'citizenship': 'Filipino',
				'age': '21',
				'gender': 'female',
				'email_address': 'patient-picker@test.com',
				'mobile_number': '+639171234567',
				'telephone_number': '',
				'designation': 'student',
				'institution_id': 'P-1001',
				'department_college_office': 'BSN - College of Nursing',
				'course': 'BSN',
				'year_level': '',
				'position': '',
				'specialization': '',
				'license_number': '',
				'ptr_no': '',
				'blood_type': '',
				'medical_conditions': '',
				'guardian_name': 'Parent Name',
				'guardian_contact': '+639179876543',
			},
			follow=True,
		)
		self.assertEqual(response.status_code, 200)
		created = HealthProfileForm.objects.latest('created_at')
		self.assertEqual(created.user_id, self.patient.id)

	def test_create_prescription_uses_selected_patient_user(self):
		response = self.client.post(
			reverse('health_forms_services:create_prescription'),
			{
				'selected_user_id': str(self.patient.id),
				'patient_name': 'Ana Patient',
				'age': '21',
				'gender': 'female',
				'address': '123 Main St',
				'date': '',
				'diagnosis': '',
				'medications': '',
				'instructions': '',
				'physician_name': '',
				'license_no': '',
				'ptr_no': '',
			},
			follow=True,
		)
		self.assertEqual(response.status_code, 200)
		created = Prescription.objects.latest('created_at')
		self.assertEqual(created.user_id, self.patient.id)

	def test_manual_entry_page_includes_patient_picker_script(self):
		response = self.client.get(reverse('health_forms_services:manual_entry'))
		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'hf-patient-picker.js')
		self.assertContains(response, 'hfPatientPicker')
		self.assertContains(response, 'id="hf-picker-config"')
		self.assertContains(response, 'Search by name, email, or patient ID')
		self.assertContains(response, 'name="selected_user_id"')

	def test_create_dental_form_page_includes_patient_picker_ui(self):
		response = self.client.get(reverse('health_forms_services:create_dental_form'))
		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'id="hf-picker-config"')
		self.assertContains(response, 'Search by name, email, or patient ID')
