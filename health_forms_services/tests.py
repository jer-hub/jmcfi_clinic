import re

from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.models import PatientProfile, StaffProfile, User
from core.guest_auth import create_guest_user
from health_forms_services.forms import (
	DIAGNOSTIC_TEST_TRIPLETS,
	DentalHealthPersonalInfoForm,
	DentalServicesPersonalInfoForm,
	HealthProfileClinicalSummaryForm,
	IMMUNIZATION_FLAG_DATE_PAIRS,
	PatientChartPersonalInfoForm,
	join_prescription_body,
	split_prescription_body,
)
from health_forms_services.forms import HealthProfilePersonalInfoForm
from health_forms_services.models import (
	DentalHealthForm,
	DentalServicesRequest,
	HealthProfileForm,
	PatientChart,
	PatientChartEntry,
	Prescription,
	PrescriptionItem,
)


def _complete_staff_like_profile(user, staff_id, department='Clinic Operations'):
	profile, _ = StaffProfile.objects.get_or_create(user=user)
	profile.staff_id = staff_id
	profile.department = department
	profile.phone = '09123456789'
	profile.save()
	return profile


class HealthProfileClinicalSummaryFormTests(TestCase):
	def setUp(self):
		self.doctor = User.objects.create_user(
			email='doctor-clinical-form@test.com',
			password='DoctorPass123!',
			role='doctor',
			is_staff=True,
			is_active=True,
			first_name='Current',
			last_name='Doctor',
		)
		_complete_staff_like_profile(self.doctor, 'DOC-HF-CLIN-001')
		self.patient = User.objects.create_user(
			email='patient-clinical-form@test.com',
			password='PatientPass123!',
			role='patient',
			is_active=True,
		)
		self.health_form = HealthProfileForm.objects.create(user=self.patient)

	def test_defaults_examining_physician_to_logged_in_doctor_when_empty(self):
		form = HealthProfileClinicalSummaryForm(instance=self.health_form, user=self.doctor)
		self.assertEqual(form.initial.get('examining_physician'), self.doctor.pk)

	def test_does_not_override_existing_examining_physician(self):
		other_doctor = User.objects.create_user(
			email='doctor-clinical-form-existing@test.com',
			password='DoctorPass123!',
			role='doctor',
			is_staff=True,
			is_active=True,
			first_name='Existing',
			last_name='Doctor',
		)
		_complete_staff_like_profile(other_doctor, 'DOC-HF-CLIN-002')
		self.health_form.examining_physician = other_doctor
		self.health_form.save(update_fields=['examining_physician'])
		form = HealthProfileClinicalSummaryForm(instance=self.health_form, user=self.doctor)
		self.assertNotEqual(form.initial.get('examining_physician'), self.doctor.pk)

	def test_defaults_examination_date_to_today_when_empty(self):
		form = HealthProfileClinicalSummaryForm(instance=self.health_form, user=self.doctor)
		self.assertEqual(form.initial.get('examination_date'), timezone.localdate())

	def test_does_not_override_existing_examination_date(self):
		self.health_form.examination_date = timezone.localdate().replace(day=1)
		self.health_form.save(update_fields=['examination_date'])
		form = HealthProfileClinicalSummaryForm(instance=self.health_form, user=self.doctor)
		self.assertEqual(form.initial.get('examination_date'), self.health_form.examination_date)


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
		from core.doctor_access import ALL_MODULE_KEYS

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
		doc_profile = self.doctor.staff_profile
		doc_profile.allowed_clinical_modules = list(ALL_MODULE_KEYS)
		doc_profile.save(update_fields=['allowed_clinical_modules'])

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
				'zip_code': '1000',
				'phone': '09171234567',
				'telephone_number': '0281234567',
				'emergency_contact': 'Parent Name',
				'emergency_phone': '09179876543',
				'course': 'BSN',
				'department': 'College of Nursing',
				'age': 21,
				'blood_type': 'O+',
				'allergies': 'Peanuts',
				'medical_conditions': 'Asthma',
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

	def test_search_patients_excludes_guests(self):
		from core.guest_auth import create_guest_user

		guest = create_guest_user(first_name='Ana', last_name='Guest')
		response = self.client.get(
			reverse('health_forms_services:search_patients'),
			{'q': 'Ana'},
		)
		self.assertEqual(response.status_code, 200)
		ids = {row['id'] for row in response.json()['results']}
		self.assertIn(self.patient.id, ids)
		self.assertNotIn(guest.id, ids)

	def test_patient_profile_prefill_endpoint_returns_expected_fields(self):
		from core.doctor_access import ALL_MODULE_KEYS
		profile = self.doctor.staff_profile
		profile.allowed_clinical_modules = list(ALL_MODULE_KEYS)
		profile.save(update_fields=['allowed_clinical_modules'])

		response = self.client.get(
			reverse('health_forms_services:patient_profile_prefill', args=[self.patient.id]),
		)
		self.assertEqual(response.status_code, 200)
		payload = response.json()
		self.assertEqual(payload['first_name'], 'Ana')
		self.assertEqual(payload['last_name'], 'Patient')
		self.assertEqual(payload['contact_number'], '09171234567')
		self.assertEqual(payload['department_college_office'], 'College of Nursing')
		self.assertEqual(payload['guardian_name'], 'Parent Name')
		self.assertEqual(payload['blood_type'], 'O+')
		self.assertEqual(payload['allergies'], 'Peanuts')
		self.assertEqual(payload['medical_conditions'], 'Asthma')
		self.assertEqual(payload['zip_code'], '1000')

	def test_patient_profile_prefill_marks_walk_in_as_guest(self):
		from core.doctor_access import ALL_MODULE_KEYS
		profile = self.doctor.staff_profile
		profile.allowed_clinical_modules = list(ALL_MODULE_KEYS)
		profile.save(update_fields=['allowed_clinical_modules'])

		walk_in_user = create_guest_user(first_name='Walk', last_name='Guest')
		PatientProfile.objects.filter(user=walk_in_user).update(
			department='College of Nursing',
			course='BSN',
			year_level='4th Year',
		)
		response = self.client.get(
			reverse('health_forms_services:patient_profile_prefill', args=[walk_in_user.id]),
		)
		self.assertEqual(response.status_code, 200)
		payload = response.json()
		self.assertEqual(payload['designation'], 'guest')
		self.assertEqual(payload['department_college_office'], '')
		self.assertEqual(payload['course'], '')
		self.assertEqual(payload['year_level'], '')

	def test_health_profile_picker_mappings_include_medical_fields(self):
		from health_forms_services.picker_mappings import picker_field_mappings

		mappings = picker_field_mappings('health_profile')
		self.assertEqual(mappings.get('blood_type'), 'blood_type')
		self.assertEqual(mappings.get('allergies'), 'allergies')
		self.assertEqual(mappings.get('medical_conditions'), 'medical_conditions')

	def test_dental_form_picker_maps_department_from_college_key(self):
		from health_forms_services.picker_mappings import picker_field_mappings

		mappings = picker_field_mappings('dental_form')
		self.assertEqual(mappings.get('department'), 'department_college_office')
		self.assertEqual(
			picker_field_mappings('dental_services').get('department_college_office'),
			'department_college_office',
		)

	def test_create_patient_chart_page_uses_grouped_sections(self):
		response = self.client.get(reverse('health_forms_services:create_patient_chart'))
		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Name &amp; Demographics')
		self.assertContains(response, 'Address &amp; Birth')
		self.assertContains(response, 'Designation')
		self.assertContains(response, 'In Case of Emergency')

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

	def test_create_dental_form_uses_selected_patient_user(self):
		response = self.client.post(
			reverse('health_forms_services:create_dental_form'),
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

	def test_invalid_selected_user_is_rejected(self):
		response = self.client.post(
			reverse('health_forms_services:create_dental_services'),
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

	def test_invalid_selected_user_is_rejected_for_dental_form(self):
		response = self.client.post(
			reverse('health_forms_services:create_dental_form'),
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

	def test_create_health_profile_walk_in_on_submit_from_profiling(self):
		from core.guest_auth import is_guest_user

		response = self.client.post(
			reverse('health_forms_services:manual_entry'),
			{
				'register_guest': '1',
				'last_name': 'Reyes',
				'first_name': 'Ana',
				'middle_name': '',
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
				'email_address': 'walkin-create@test.com',
				'mobile_number': '+639171234567',
				'telephone_number': '',
				'designation': 'guest',
				'institution_id': '',
				'department_college_office': '',
				'course': '',
				'year_level': '',
				'position': '',
				'specialization': '',
				'license_number': '',
				'ptr_no': '',
				'blood_type': '',
				'medical_conditions': '',
				'guardian_name': '',
				'guardian_contact': '',
			},
			follow=True,
		)
		self.assertEqual(response.status_code, 200)
		created = HealthProfileForm.objects.latest('created_at')
		self.assertTrue(is_guest_user(created.user))
		self.assertEqual(created.user.first_name, 'Ana')
		self.assertEqual(created.user.last_name, 'Reyes')
		self.assertEqual(created.last_name, 'Reyes')
		self.assertEqual(created.user.patient_profile.contact_email, 'walkin-create@test.com')

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

	def test_create_prescription_defaults_physician_for_logged_in_doctor(self):
		profile = self.doctor.staff_profile
		profile.license_number = '123123'
		profile.ptr_no = '22333'
		profile.save(update_fields=['license_number', 'ptr_no'])

		response = self.client.get(reverse('health_forms_services:create_prescription'))
		self.assertEqual(response.status_code, 200)
		form = response.context['form']
		self.assertEqual(form.initial.get('physician'), self.doctor.pk)
		self.assertEqual(form.initial.get('physician_name'), self.doctor.get_full_name())
		self.assertEqual(form.initial.get('license_no'), '123123')
		self.assertEqual(form.initial.get('ptr_no'), '22333')
		self.assertContains(
			response,
			f'<option value="{self.doctor.pk}" selected',
			html=False,
		)

	def test_create_prescription_leaves_physician_blank_for_staff(self):
		staff = User.objects.create_user(
			email='staff-picker@test.com',
			password='StaffPass123!',
			role='staff',
			is_staff=True,
			is_active=True,
			first_name='Clinic',
			last_name='Staff',
		)
		_complete_staff_like_profile(staff, 'STAFF-HF-001')
		self.client.force_login(staff)

		response = self.client.get(reverse('health_forms_services:create_prescription'))
		self.assertEqual(response.status_code, 200)
		form = response.context['form']
		self.assertIsNone(form.initial.get('physician'))
		self.assertContains(response, 'Select physician')
		self.assertNotContains(
			response,
			f'<option value="{self.doctor.pk}" selected',
			html=False,
		)

	def test_create_prescription_saves_selected_physician_for_staff(self):
		staff = User.objects.create_user(
			email='staff-rx@test.com',
			password='StaffPass123!',
			role='staff',
			is_staff=True,
			is_active=True,
			first_name='Clinic',
			last_name='Staff',
		)
		_complete_staff_like_profile(staff, 'STAFF-HF-002')
		profile = self.doctor.staff_profile
		profile.license_number = '123123'
		profile.ptr_no = '22333'
		profile.save(update_fields=['license_number', 'ptr_no'])
		self.client.force_login(staff)

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
				'physician': str(self.doctor.pk),
				'physician_name': '',
				'license_no': '',
				'ptr_no': '',
			},
			follow=True,
		)
		self.assertEqual(response.status_code, 200)
		created = Prescription.objects.latest('created_at')
		self.assertEqual(created.physician_name, self.doctor.get_full_name())
		self.assertEqual(created.license_no, '123123')
		self.assertEqual(created.ptr_no, '22333')

	def test_create_prescription_defaults_physician_for_logged_in_doctor(self):
		profile = self.doctor.staff_profile
		profile.license_number = '123123'
		profile.ptr_no = '22333'
		profile.save(update_fields=['license_number', 'ptr_no'])

		response = self.client.get(reverse('health_forms_services:create_prescription'))
		self.assertEqual(response.status_code, 200)
		form = response.context['form']
		self.assertEqual(form.initial.get('physician'), self.doctor.pk)
		self.assertEqual(form.initial.get('physician_name'), self.doctor.get_full_name())
		self.assertEqual(form.initial.get('license_no'), '123123')
		self.assertEqual(form.initial.get('ptr_no'), '22333')
		self.assertContains(
			response,
			f'<option value="{self.doctor.pk}" selected',
			html=False,
		)

	def test_create_prescription_leaves_physician_blank_for_staff(self):
		staff = User.objects.create_user(
			email='staff-picker@test.com',
			password='StaffPass123!',
			role='staff',
			is_staff=True,
			is_active=True,
			first_name='Clinic',
			last_name='Staff',
		)
		_complete_staff_like_profile(staff, 'STAFF-HF-001')
		self.client.force_login(staff)

		response = self.client.get(reverse('health_forms_services:create_prescription'))
		self.assertEqual(response.status_code, 200)
		form = response.context['form']
		self.assertIsNone(form.initial.get('physician'))
		self.assertContains(response, 'Select physician')
		self.assertNotContains(
			response,
			f'<option value="{self.doctor.pk}" selected',
			html=False,
		)

	def test_create_prescription_saves_selected_physician_for_staff(self):
		staff = User.objects.create_user(
			email='staff-rx@test.com',
			password='StaffPass123!',
			role='staff',
			is_staff=True,
			is_active=True,
			first_name='Clinic',
			last_name='Staff',
		)
		_complete_staff_like_profile(staff, 'STAFF-HF-002')
		profile = self.doctor.staff_profile
		profile.license_number = '123123'
		profile.ptr_no = '22333'
		profile.save(update_fields=['license_number', 'ptr_no'])
		self.client.force_login(staff)

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
				'physician': str(self.doctor.pk),
				'physician_name': '',
				'license_no': '',
				'ptr_no': '',
			},
			follow=True,
		)
		self.assertEqual(response.status_code, 200)
		created = Prescription.objects.latest('created_at')
		self.assertEqual(created.physician_name, self.doctor.get_full_name())
		self.assertEqual(created.license_no, '123123')
		self.assertEqual(created.ptr_no, '22333')

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


@override_settings(
	MIDDLEWARE=[
		middleware
		for middleware in settings.MIDDLEWARE
		if middleware != 'core.middleware.ProfileCompleteMiddleware'
	]
)
class HealthFormSectionSaveTests(TestCase):
	def setUp(self):
		self.doctor = User.objects.create_user(
			email='doctor-save@test.com',
			password='DoctorPass123!',
			role='doctor',
			is_staff=True,
			is_active=True,
			first_name='Save',
			last_name='Doctor',
		)
		_complete_staff_like_profile(self.doctor, 'DOC-SAVE-001')
		self.patient = User.objects.create_user(
			email='patient-save@test.com',
			password='PatientPass123!',
			role='patient',
			is_active=True,
			first_name='Jane',
			last_name='Doe',
		)
		self.health_form = HealthProfileForm.objects.create(
			user=self.patient,
			last_name='Doe',
			first_name='Jane',
			email_address='patient-save@test.com',
			mobile_number='+639171234567',
			designation='student',
			department_college_office='College of Nursing',
			date_of_birth='2000-01-15',
			gender='female',
		)
		PatientProfile.objects.update_or_create(
			user=self.patient,
			defaults={
				'patient_id': 'PAT-SAVE-001',
				'blood_type': '',
				'medical_conditions': '',
			},
		)
		self.client.force_login(self.doctor)
		self.edit_url = reverse('health_forms_services:edit_form', args=[self.health_form.pk])

	def _personal_post_data(self, **overrides):
		data = {
			'section': 'personal',
			'last_name': 'Doe',
			'first_name': 'Jane',
			'middle_name': '',
			'permanent_address': '',
			'zip_code': '',
			'current_address': '',
			'religion': '',
			'civil_status': '',
			'place_of_birth': '',
			'date_of_birth': '2000-01-15',
			'citizenship': '',
			'age': '',
			'gender': 'female',
			'email_address': 'patient-save@test.com',
			'mobile_number': '+639171234567',
			'telephone_number': '',
			'designation': 'student',
			'institution_id': '',
			'department_college_office': 'College of Nursing',
			'course': '',
			'year_level': '',
			'position': '',
			'specialization': '',
			'license_number': '',
			'ptr_no': '',
			'blood_type': '',
			'medical_conditions': '',
			'guardian_name': '',
			'guardian_contact': '',
		}
		data.update(overrides)
		return data

	def test_edit_page_includes_section_save_script(self):
		response = self.client.get(self.edit_url)
		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'health-form-edit.js')
		self.assertContains(response, 'data-section-save="ajax"')

	def test_ajax_section_save_returns_json_and_persists(self):
		response = self.client.post(
			self.edit_url,
			self._medical_post_data(allergies='Sulfa drugs'),
			HTTP_X_REQUESTED_WITH='XMLHttpRequest',
		)
		self.assertEqual(response.status_code, 200)
		payload = response.json()
		self.assertTrue(payload['success'])
		self.assertEqual(payload['section'], 'medical')
		self.health_form.refresh_from_db()
		self.assertEqual(self.health_form.allergies, 'Sulfa drugs')

	def test_personal_section_ajax_save_is_read_only(self):
		response = self.client.post(
			self.edit_url,
			self._personal_post_data(first_name='Janet'),
			HTTP_X_REQUESTED_WITH='XMLHttpRequest',
		)
		self.assertEqual(response.status_code, 403)
		payload = response.json()
		self.assertFalse(payload['success'])
		self.health_form.refresh_from_db()
		self.assertEqual(self.health_form.first_name, 'Jane')

	def test_edit_personal_fields_are_readonly(self):
		response = self.client.get(self.edit_url + '?section=personal')
		self.assertEqual(response.status_code, 200)
		content = response.content.decode()
		self.assertIn('Personal information is read-only', content)
		self.assertRegex(
			content,
			r'<form[^>]*data-section="personal"[^>]*data-section-readonly="1"',
		)
		self.assertNotRegex(
			content,
			r'<form[^>]*data-section="personal"[^>]*data-section-save="ajax"',
		)
		first_name_match = re.search(r'<input[^>]*name="first_name"[^>]*>', content)
		designation_match = re.search(r'<input[^>]*type="hidden"[^>]*id="id_designation"[^>]*>', content)
		self.assertIsNotNone(first_name_match)
		self.assertIsNotNone(designation_match)
		self.assertIn('disabled', first_name_match.group(0))
		self.assertIn('data-list-field-readonly="1"', content)

	def test_ajax_invalid_section_returns_field_errors(self):
		response = self.client.post(
			self.edit_url,
			self._medical_post_data(menarche_age='not-a-number'),
			HTTP_X_REQUESTED_WITH='XMLHttpRequest',
		)
		self.assertEqual(response.status_code, 400)
		payload = response.json()
		self.assertFalse(payload['success'])
		self.assertIn('menarche_age', payload['errors'])

	def test_non_ajax_save_redirects_to_edit_with_section(self):
		response = self.client.post(
			self.edit_url,
			self._medical_post_data(allergies='Aspirin'),
		)
		self.assertRedirects(
			response,
			f'{self.edit_url}?section=medical',
			fetch_redirect_response=False,
		)
		self.health_form.refresh_from_db()
		self.assertEqual(self.health_form.allergies, 'Aspirin')

	def test_physical_section_save_calculates_bmi(self):
		response = self.client.post(
			self.edit_url,
			{
				'section': 'physical',
				'blood_pressure': '',
				'heart_rate': '',
				'respiratory_rate': '',
				'temperature': '',
				'spo2': '',
				'height': '1.70',
				'weight': '65',
				'bmi': '',
				'bmi_remarks': '',
				'exam_general': '',
				'exam_heent': '',
				'exam_chest_lungs': '',
				'exam_abdomen': '',
				'exam_genitourinary': '',
				'exam_extremities': '',
				'exam_neurologic': '',
				'exam_other_findings': '',
			},
			HTTP_X_REQUESTED_WITH='XMLHttpRequest',
		)
		self.assertEqual(response.status_code, 200)
		self.assertTrue(response.json()['success'])
		self.health_form.refresh_from_db()
		self.assertEqual(float(self.health_form.bmi), 22.49)
		self.assertEqual(self.health_form.bmi_remarks, 'Normal')

	def _ajax_save(self, data):
		return self.client.post(
			self.edit_url,
			data,
			HTTP_X_REQUESTED_WITH='XMLHttpRequest',
		)

	def _medical_post_data(self, **overrides):
		data = {
			'section': 'medical',
			'immunization_others': 'Tdap booster',
			'illness_others': 'Seasonal rhinitis',
			'menarche_age': '12',
			'menstrual_duration': '4 days',
			'menstrual_interval': '28 days',
			'menstrual_amount': 'moderate',
			'menstrual_symptoms': 'Mild cramping',
			'obstetric_history': 'G0P0',
			'allergies': 'Penicillin',
			'current_medications': 'Vitamin D',
			'present_illness': 'None',
		}
		for flag, date_field in IMMUNIZATION_FLAG_DATE_PAIRS:
			data[flag] = 'on'
			data[date_field] = '2024-06-01'
		for name in (
			'illness_measles',
			'illness_mumps',
			'illness_rubella',
			'illness_chickenpox',
			'illness_ptb_pki',
			'illness_hypertension',
			'illness_diabetes',
			'illness_asthma',
		):
			data[name] = 'on'
		data.update(overrides)
		return data

	def _diagnostic_post_data(self, **overrides):
		data = {'section': 'diagnostic', 'test_others': 'ECG normal sinus rhythm'}
		for flag, date_field, findings_field in DIAGNOSTIC_TEST_TRIPLETS:
			data[flag] = 'on'
			data[date_field] = '2024-07-15'
			data[findings_field] = f'{flag} findings'
		data.update(overrides)
		return data

	def _physical_post_data(self, **overrides):
		data = {
			'section': 'physical',
			'blood_pressure': '118/76',
			'heart_rate': '72',
			'respiratory_rate': '16',
			'temperature': '36.6',
			'spo2': '98.5',
			'height': '1.65',
			'weight': '58',
			'bmi': '',
			'bmi_remarks': '',
			'exam_general': 'Well-nourished, alert',
			'exam_heent': 'PERRLA',
			'exam_chest_lungs': 'Clear breath sounds',
			'exam_abdomen': 'Soft, non-tender',
			'exam_genitourinary': 'Unremarkable',
			'exam_extremities': 'Full ROM',
			'exam_neurologic': 'CN II-XII intact',
			'exam_other_findings': 'No acute distress',
		}
		data.update(overrides)
		return data

	def _clinical_post_data(self, **overrides):
		data = {
			'section': 'clinical',
			'physician_impression': 'Fit for school activities',
			'final_remarks': 'No contraindications noted',
			'recommendations': 'Annual follow-up',
			'examining_physician': str(self.doctor.pk),
			'examination_date': '2024-08-01',
		}
		data.update(overrides)
		return data

	def test_personal_section_saves_all_fields(self):
		response = self._ajax_save(self._personal_post_data(
			middle_name='Marie',
			permanent_address='123 Main St, Manila',
			zip_code='1000',
			current_address='123 Main St, Manila',
			religion='Roman Catholic',
			civil_status='single',
			place_of_birth='Manila',
			citizenship='Filipino',
			age='24',
			telephone_number='+639181112233',
			institution_id='2024-00042',
			course='BS Nursing',
			year_level='3rd Year',
			blood_type='O+',
			medical_conditions='None known',
			guardian_name='John Doe Sr.',
			guardian_contact='+639191112233',
		))
		self.assertEqual(response.status_code, 403, response.content)
		self.assertFalse(response.json()['success'])
		self.assertEqual(response.json()['error'], 'Personal Info section is read-only.')

	def test_personal_section_syncs_medical_background_to_patient_profile(self):
		response = self._ajax_save(self._personal_post_data(
			blood_type='B+',
			medical_conditions='Hypertension',
		))
		self.assertEqual(response.status_code, 403, response.content)
		self.assertFalse(response.json()['success'])
		self.assertEqual(response.json()['error'], 'Personal Info section is read-only.')

	def test_personal_phone_fields_reject_invalid_format(self):
		from health_forms_services.forms import HealthProfilePersonalInfoForm

		for field in ('mobile_number', 'telephone_number', 'guardian_contact'):
			with self.subTest(field=field):
				data = self._personal_post_data(**{field: '12345'})
				form = HealthProfilePersonalInfoForm(data, instance=self.health_form)
				self.assertFalse(form.is_valid())
				self.assertIn(field, form.errors)

	def test_personal_phone_fields_accept_local_format(self):
		from health_forms_services.forms import HealthProfilePersonalInfoForm

		data = self._personal_post_data(mobile_number='09171234567')
		form = HealthProfilePersonalInfoForm(data, instance=self.health_form)
		self.assertTrue(form.is_valid(), form.errors)
		self.assertEqual(form.cleaned_data['mobile_number'], '+639171234567')
		self.assertEqual(
			form.fields['mobile_number'].widget.attrs.get('data-phone-badge'),
			'true',
		)

	def test_medical_section_saves_all_fields(self):
		response = self._ajax_save(self._medical_post_data())
		self.assertEqual(response.status_code, 200, response.content)
		self.assertTrue(response.json()['success'])
		self.health_form.refresh_from_db()
		self.assertTrue(self.health_form.immunization_covid19)
		self.assertEqual(str(self.health_form.immunization_covid19_date), '2024-06-01')
		self.assertTrue(self.health_form.illness_hypertension)
		self.assertEqual(self.health_form.allergies, 'Penicillin')
		self.assertEqual(self.health_form.menarche_age, 12)
		self.assertEqual(self.health_form.immunization_others, 'Tdap booster')

	def test_medical_section_syncs_allergies_to_patient_profile(self):
		response = self._ajax_save(self._medical_post_data(allergies='Peanut'))
		self.assertEqual(response.status_code, 200, response.content)
		self.assertTrue(response.json()['success'])
		profile = PatientProfile.objects.get(user=self.patient)
		self.assertEqual(profile.allergies, 'Peanut')

	def test_medical_immunization_checked_without_date_returns_error(self):
		data = self._medical_post_data()
		del data['immunization_covid19_date']
		response = self._ajax_save(data)
		self.assertEqual(response.status_code, 400)
		self.assertIn('immunization_covid19_date', response.json()['errors'])

	def test_medical_unchecked_immunization_clears_stored_date(self):
		self._ajax_save(self._medical_post_data())
		self.health_form.refresh_from_db()
		self.assertTrue(self.health_form.immunization_covid19)
		data = self._medical_post_data()
		data.pop('immunization_covid19', None)
		data.pop('immunization_covid19_date', None)
		response = self._ajax_save(data)
		self.assertEqual(response.status_code, 200, response.content)
		self.health_form.refresh_from_db()
		self.assertFalse(self.health_form.immunization_covid19)
		self.assertIsNone(self.health_form.immunization_covid19_date)

	def test_diagnostic_section_saves_all_fields(self):
		response = self._ajax_save(self._diagnostic_post_data())
		self.assertEqual(response.status_code, 200, response.content)
		self.assertTrue(response.json()['success'])
		self.health_form.refresh_from_db()
		self.assertTrue(self.health_form.test_cbc)
		self.assertEqual(str(self.health_form.test_cbc_date), '2024-07-15')
		self.assertEqual(self.health_form.test_cbc_findings, 'test_cbc findings')
		self.assertEqual(self.health_form.test_others, 'ECG normal sinus rhythm')

	def test_diagnostic_checked_without_date_returns_error(self):
		data = self._diagnostic_post_data()
		del data['test_cbc_date']
		response = self._ajax_save(data)
		self.assertEqual(response.status_code, 400)
		self.assertIn('test_cbc_date', response.json()['errors'])

	def test_diagnostic_checked_without_findings_returns_error(self):
		data = self._diagnostic_post_data()
		del data['test_cbc_findings']
		response = self._ajax_save(data)
		self.assertEqual(response.status_code, 400)
		self.assertIn('test_cbc_findings', response.json()['errors'])

	def test_diagnostic_unchecked_test_clears_date_and_findings(self):
		self._ajax_save(self._diagnostic_post_data())
		self.health_form.refresh_from_db()
		self.assertTrue(self.health_form.test_cbc)
		data = self._diagnostic_post_data()
		data.pop('test_cbc', None)
		data.pop('test_cbc_date', None)
		data.pop('test_cbc_findings', None)
		response = self._ajax_save(data)
		self.assertEqual(response.status_code, 200, response.content)
		self.health_form.refresh_from_db()
		self.assertFalse(self.health_form.test_cbc)
		self.assertIsNone(self.health_form.test_cbc_date)
		self.assertEqual(self.health_form.test_cbc_findings, '')

	def test_physical_section_saves_all_fields(self):
		response = self._ajax_save(self._physical_post_data())
		self.assertEqual(response.status_code, 200, response.content)
		self.assertTrue(response.json()['success'])
		self.health_form.refresh_from_db()
		self.assertEqual(self.health_form.blood_pressure, '118/76')
		self.assertEqual(self.health_form.heart_rate, 72)
		self.assertEqual(float(self.health_form.temperature), 36.6)
		self.assertEqual(self.health_form.exam_neurologic, 'CN II-XII intact')
		self.assertEqual(float(self.health_form.bmi), 21.30)

	def test_clinical_section_saves_all_fields(self):
		response = self._ajax_save(self._clinical_post_data())
		self.assertEqual(response.status_code, 200, response.content)
		self.assertTrue(response.json()['success'])
		self.health_form.refresh_from_db()
		self.assertEqual(self.health_form.physician_impression, 'Fit for school activities')
		self.assertEqual(self.health_form.examining_physician_id, self.doctor.pk)
		self.assertEqual(str(self.health_form.examination_date), '2024-08-01')

	def test_all_sections_save_in_sequence_without_data_loss(self):
		sections = [
			(self._medical_post_data(allergies='Seq allergy'), 'allergies', 'Seq allergy'),
			(self._physical_post_data(exam_general='Seq exam'), 'exam_general', 'Seq exam'),
			(self._diagnostic_post_data(test_others='Seq tests'), 'test_others', 'Seq tests'),
			(self._clinical_post_data(final_remarks='Seq remarks'), 'final_remarks', 'Seq remarks'),
		]
		for data, field, expected in sections:
			with self.subTest(section=data['section'], field=field):
				response = self._ajax_save(data)
				self.assertEqual(response.status_code, 200, response.content)
				self.assertTrue(response.json()['success'])
				self.health_form.refresh_from_db()
				self.assertEqual(getattr(self.health_form, field), expected)
		self.assertEqual(self.health_form.allergies, 'Seq allergy')


@override_settings(
	MIDDLEWARE=[
		middleware
		for middleware in settings.MIDDLEWARE
		if middleware != 'core.middleware.ProfileCompleteMiddleware'
	]
)
class DentalServicesProcessFlowTests(TestCase):
	def setUp(self):
		self.doctor = User.objects.create_user(
			email='doctor-dental-svc@test.com',
			password='DoctorPass123!',
			role='doctor',
			is_staff=True,
			is_active=True,
			first_name='Dental',
			last_name='Doctor',
		)
		doctor_profile = _complete_staff_like_profile(self.doctor, 'DOC-DS-001')
		doctor_profile.license_number = 'PRC-DS-001'
		doctor_profile.save(update_fields=['license_number'])
		self.patient = User.objects.create_user(
			email='patient-dental-svc@test.com',
			password='PatientPass123!',
			role='patient',
			is_active=True,
			first_name='Ana',
			last_name='Patient',
		)
		PatientProfile.objects.update_or_create(
			user=self.patient,
			defaults={'patient_id': 'P-DS-001'},
		)
		self.request = DentalServicesRequest.objects.create(
			user=self.patient,
			last_name='Patient',
			first_name='Ana',
			middle_name='M',
			status=DentalServicesRequest.Status.PENDING,
		)
		self.client.force_login(self.doctor)

	def test_list_search_by_last_name(self):
		response = self.client.get(
			reverse('health_forms_services:dental_forms_list'),
			{'search': 'Patient'},
		)
		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Patient, Ana')

	def test_edit_page_shows_multi_tab_checklist(self):
		response = self.client.get(
			reverse('health_forms_services:edit_dental_form', args=[self.request.pk]),
		)
		self.assertEqual(response.status_code, 200)
		for label in ('Personal', 'Perio', 'Operative', 'Surgery', 'Prosth', 'Endo', 'Pediatric', 'Dentist'):
			with self.subTest(label=label):
				self.assertContains(response, label)
		for full_label in (
			'Personal Info',
			'Periodontics',
			'Prosthodontics',
			'Endodontics',
			'Dentist &amp; Other',
		):
			with self.subTest(full_label=full_label):
				self.assertContains(response, f'title="{full_label}"')

	def test_operative_section_save_persists_checkbox_and_detail(self):
		response = self.client.post(
			reverse('health_forms_services:edit_dental_form', args=[self.request.pk]),
			{
				'section': 'operative',
				'oper_class_i': 'on',
				'oper_class_i_detail': 'Tooth #16',
			},
			HTTP_X_REQUESTED_WITH='XMLHttpRequest',
		)
		self.assertEqual(response.status_code, 200)
		self.assertTrue(response.json()['success'])
		self.request.refresh_from_db()
		self.assertTrue(self.request.oper_class_i)
		self.assertEqual(self.request.oper_class_i_detail, 'Tooth #16')
		self.assertIn('Class I restoration', self.request.selected_services)

	def test_surgery_section_allows_odontectomy_without_detail(self):
		response = self.client.post(
			reverse('health_forms_services:edit_dental_form', args=[self.request.pk]),
			{
				'section': 'surgery',
				'surg_odontectomy': 'on',
			},
			HTTP_X_REQUESTED_WITH='XMLHttpRequest',
		)
		self.assertEqual(response.status_code, 200)
		self.assertTrue(response.json()['success'])
		self.request.refresh_from_db()
		self.assertTrue(self.request.surg_odontectomy)

	def test_operative_section_requires_detail_when_checked(self):
		response = self.client.post(
			reverse('health_forms_services:edit_dental_form', args=[self.request.pk]),
			{
				'section': 'operative',
				'oper_class_i': 'on',
				'oper_class_i_detail': '',
			},
			HTTP_X_REQUESTED_WITH='XMLHttpRequest',
		)
		self.assertEqual(response.status_code, 400)
		self.assertIn('oper_class_i_detail', response.json()['errors'])

	def test_perio_section_save_persists(self):
		response = self.client.post(
			reverse('health_forms_services:edit_dental_form', args=[self.request.pk]),
			{
				'section': 'perio',
				'perio_oral_prophylaxis': 'on',
			},
			HTTP_X_REQUESTED_WITH='XMLHttpRequest',
		)
		self.assertEqual(response.status_code, 200)
		self.request.refresh_from_db()
		self.assertTrue(self.request.perio_oral_prophylaxis)
		self.assertIn('Oral prophylaxis', self.request.selected_services)

	def test_detail_page_shows_selected_services(self):
		self.request.oper_class_ii = True
		self.request.oper_class_ii_detail = 'Tooth #26'
		self.request.save(update_fields=['oper_class_ii', 'oper_class_ii_detail'])
		response = self.client.get(
			reverse('health_forms_services:dental_form_detail', args=[self.request.pk]),
		)
		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Operative Dentistry')
		self.assertContains(response, 'Class II restoration')
		self.assertContains(response, 'Tooth #26')

	def test_dental_services_detail_shows_all_service_categories(self):
		response = self.client.get(
			reverse('health_forms_services:dental_form_detail', args=[self.request.pk]),
		)
		self.assertEqual(response.status_code, 200)
		for heading in (
			'Periodontics',
			'Operative Dentistry',
			'Surgery',
			'Prosthodontics',
			'Endodontics',
			'Pediatric',
			'Treatment Status',
			'Dentist Information',
		):
			with self.subTest(heading=heading):
				self.assertContains(response, heading)

	def test_dental_services_detail_hides_services_without_details(self):
		self.request.perio_oral_prophylaxis = True
		self.request.perio_scaling_root_planning = False
		self.request.oper_class_i = True
		self.request.oper_class_i_detail = ''
		self.request.save(update_fields=[
			'perio_oral_prophylaxis',
			'perio_scaling_root_planning',
			'oper_class_i',
			'oper_class_i_detail',
		])
		response = self.client.get(
			reverse('health_forms_services:dental_form_detail', args=[self.request.pk]),
		)
		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Oral prophylaxis')
		self.assertNotContains(response, 'Scaling and root planning')
		self.assertNotContains(response, 'Class I restoration')

	def test_dental_services_detail_shows_service_detail_text(self):
		self.request.surg_tooth_extraction = True
		self.request.surg_tooth_extraction_detail = 'Tooth #38'
		self.request.save(update_fields=['surg_tooth_extraction', 'surg_tooth_extraction_detail'])
		response = self.client.get(
			reverse('health_forms_services:dental_form_detail', args=[self.request.pk]),
		)
		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Tooth extraction')
		self.assertContains(response, 'Tooth #38')

	def test_dental_services_detail_shows_treatment_and_dentist_block(self):
		self.request.currently_undergoing_treatment = True
		self.request.currently_undergoing_treatment_detail = 'Orthodontic braces'
		self.request.dentist_name = 'Dr. Maria Santos'
		self.request.dentist_date = '2024-06-15'
		self.request.dentist_license_no = 'PRC-12345'
		self.request.save(update_fields=[
			'currently_undergoing_treatment',
			'currently_undergoing_treatment_detail',
			'dentist_name',
			'dentist_date',
			'dentist_license_no',
		])
		response = self.client.get(
			reverse('health_forms_services:dental_form_detail', args=[self.request.pk]),
		)
		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Currently Undergoing Treatment')
		self.assertContains(response, 'Orthodontic braces')
		self.assertContains(response, 'Dr. Maria Santos')
		self.assertContains(response, 'PRC-12345')

	def test_dental_services_detail_docx_link_visible(self):
		response = self.client.get(
			reverse('health_forms_services:dental_form_detail', args=[self.request.pk]),
		)
		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Download .docx')
		self.assertContains(
			response,
			reverse('health_forms_services:export_dental_form_docx', args=[self.request.pk]),
		)

	def test_dentist_tab_prefills_current_processing_clinician(self):
		response = self.client.get(
			reverse('health_forms_services:edit_dental_form', args=[self.request.pk]) + '?section=dentist_other',
		)
		self.assertEqual(response.status_code, 200)
		self.assertNotContains(response, 'Assign clinician')
		self.assertContains(response, 'Dental Doctor')
		self.assertContains(response, 'PRC-DS-001')

	def test_create_redirects_to_perio_tab(self):
		response = self.client.post(
			reverse('health_forms_services:create_dental_form'),
			{
				'selected_user_id': str(self.patient.id),
				'last_name': 'Searchable',
				'first_name': 'Case',
				'middle_name': '',
				'address': '',
				'age': '',
				'gender': '',
				'date_of_birth': '',
				'contact_number': '',
				'department': '',
			},
		)
		created = DentalServicesRequest.objects.latest('created_at')
		self.assertRedirects(
			response,
			reverse('health_forms_services:edit_dental_form', args=[created.pk]) + '?section=perio',
		)


@override_settings(
	MIDDLEWARE=[
		middleware
		for middleware in settings.MIDDLEWARE
		if middleware != 'core.middleware.ProfileCompleteMiddleware'
	]
)
class DentalHealthFormProcessFlowTests(TestCase):
	def setUp(self):
		self.doctor = User.objects.create_user(
			email='doctor-hss@test.com',
			password='DoctorPass123!',
			role='doctor',
			is_staff=True,
			is_active=True,
			first_name='Dental',
			last_name='Doctor',
		)
		_complete_staff_like_profile(self.doctor, 'DOC-HSS-001')
		self.doctor.staff_profile.license_number = 'PRC-HSS-001'
		self.doctor.staff_profile.save(update_fields=['license_number'])
		self.patient = User.objects.create_user(
			email='patient-hss@test.com',
			password='PatientPass123!',
			role='patient',
			is_active=True,
			first_name='Ana',
			last_name='Patient',
		)
		PatientProfile.objects.update_or_create(
			user=self.patient,
			defaults={'patient_id': 'P-HSS-001'},
		)
		self.form = DentalHealthForm.objects.create(
			user=self.patient,
			last_name='Patient',
			first_name='Ana',
			middle_name='M',
			status=DentalHealthForm.Status.PENDING,
			examined_by=self.doctor,
		)
		self.client.force_login(self.doctor)

	def test_list_search_by_last_name(self):
		response = self.client.get(
			reverse('health_forms_services:dental_services_list'),
			{'search': 'Patient'},
		)
		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Patient, Ana')

	def test_edit_page_shows_chart_tab(self):
		response = self.client.get(
			reverse('health_forms_services:edit_dental_services', args=[self.form.pk]),
		)
		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Dental Chart')
		self.assertContains(response, 'Examination')
		self.assertContains(response, 'Conditions')

	def test_examination_section_save_persists(self):
		response = self.client.post(
			reverse('health_forms_services:edit_dental_services', args=[self.form.pk]),
			{
				'section': 'examination',
				'soft_tissue_lips': 'Normal',
				'presence_of_debris': 'on',
				'teeth_present': '28',
				'gingival_inflammation': 'slight',
				'occlusion': 'class_i',
			},
			HTTP_X_REQUESTED_WITH='XMLHttpRequest',
		)
		self.assertEqual(response.status_code, 200)
		self.assertTrue(response.json()['success'])
		self.form.refresh_from_db()
		self.assertEqual(self.form.soft_tissue_lips, 'Normal')
		self.assertTrue(self.form.presence_of_debris)
		self.assertEqual(self.form.teeth_present, 28)
		self.assertEqual(self.form.gingival_inflammation, 'slight')
		self.assertEqual(self.form.occlusion, 'class_i')

	def test_conditions_section_save_persists(self):
		response = self.client.post(
			reverse('health_forms_services:edit_dental_services', args=[self.form.pk]),
			{
				'section': 'conditions',
				'cond_needs_oral_prophylaxis': 'on',
				'cond_others': '',
				'cond_others_detail': '',
				'remarks': 'Follow up in 2 weeks',
				'dentist_user': str(self.doctor.pk),
				'dentist_name': '',
				'dentist_license_no': '',
			},
			HTTP_X_REQUESTED_WITH='XMLHttpRequest',
		)
		self.assertEqual(response.status_code, 200)
		self.assertTrue(response.json()['success'])
		self.form.refresh_from_db()
		self.assertTrue(self.form.cond_needs_oral_prophylaxis)
		self.assertEqual(self.form.remarks, 'Follow up in 2 weeks')
		self.assertEqual(self.form.dentist_name, self.doctor.get_full_name())
		self.assertEqual(self.form.dentist_license_no, 'PRC-HSS-001')

	def test_conditions_tab_defaults_attending_dentist_for_doctor(self):
		response = self.client.get(
			reverse('health_forms_services:edit_dental_services', args=[self.form.pk]) + '?section=conditions',
		)
		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Select Dentist')
		self.assertContains(
			response,
			f'value="{self.doctor.pk}" selected',
			html=False,
		)

	def test_conditions_tab_leaves_dentist_blank_for_staff(self):
		staff = User.objects.create_user(
			email='staff-hss@test.com',
			password='StaffPass123!',
			role='staff',
			is_staff=True,
			is_active=True,
			first_name='Clinic',
			last_name='Staff',
		)
		_complete_staff_like_profile(staff, 'STAFF-HSS-001')
		self.client.force_login(staff)
		response = self.client.get(
			reverse('health_forms_services:edit_dental_services', args=[self.form.pk]) + '?section=conditions',
		)
		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Select Dentist')
		self.assertNotContains(
			response,
			f'value="{self.doctor.pk}" selected',
			html=False,
		)

	def test_chart_api_update_persists(self):
		response = self.client.post(
			reverse('health_forms_services:dental_chart_api_update', args=[self.form.pk]),
			{
				'tooth_number': '16',
				'condition': 'decayed',
				'notes': 'Mesial caries',
			},
		)
		self.assertEqual(response.status_code, 200)
		self.assertTrue(response.json()['success'])
		self.assertEqual(self.form.dental_chart.count(), 1)
		tooth = self.form.dental_chart.get()
		self.assertEqual(tooth.tooth_number, 16)
		self.assertEqual(tooth.condition, 'decayed')

	def test_detail_page_shows_hss_sections(self):
		self.form.soft_tissue_lips = 'Normal'
		self.form.presence_of_debris = True
		self.form.teeth_present = 28
		self.form.gingival_inflammation = 'moderate'
		self.form.occlusion = 'class_i'
		self.form.cond_needs_oral_prophylaxis = True
		self.form.remarks = 'Follow up in 2 weeks'
		self.form.dentist_name = 'Dr. Dental Doctor'
		self.form.save(update_fields=[
			'soft_tissue_lips',
			'presence_of_debris',
			'teeth_present',
			'gingival_inflammation',
			'occlusion',
			'cond_needs_oral_prophylaxis',
			'remarks',
			'dentist_name',
		])
		response = self.client.get(
			reverse('health_forms_services:dental_services_detail', args=[self.form.pk]),
		)
		self.assertEqual(response.status_code, 200)
		for heading in (
			'Personal Information',
			'Initial Soft Tissue Exam',
			'Oral Health Condition',
			'Tooth Count (DMF)',
			'Initial Periodontal Exam',
			'Clinical Data',
			'Conditions &amp; Recommendations',
			'Remarks &amp; Dentist',
			'Dental Chart (FDI Notation)',
		):
			with self.subTest(heading=heading):
				self.assertContains(response, heading)

	def test_detail_docx_link_visible(self):
		response = self.client.get(
			reverse('health_forms_services:dental_services_detail', args=[self.form.pk]),
		)
		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Download .docx')
		self.assertContains(
			response,
			reverse('health_forms_services:export_dental_services_docx', args=[self.form.pk]),
		)

	def test_create_redirects_to_chart_tab(self):
		response = self.client.post(
			reverse('health_forms_services:create_dental_services'),
			{
				'selected_user_id': str(self.patient.id),
				'last_name': 'Searchable',
				'first_name': 'Case',
				'middle_name': '',
				'age': '',
				'gender': '',
				'civil_status': '',
				'address': '',
				'date_of_birth': '',
				'place_of_birth': '',
				'email_address': 'case@test.com',
				'contact_number': '',
				'telephone_number': '',
				'designation': '',
				'department_college_office': '',
				'guardian_name': '',
				'guardian_contact': '',
				'date_of_examination': '',
			},
		)
		created = DentalHealthForm.objects.latest('created_at')
		self.assertEqual(created.examined_by_id, self.doctor.id)
		self.assertRedirects(
			response,
			reverse('health_forms_services:edit_dental_services', args=[created.pk]) + '?section=chart',
		)


@override_settings(
	MIDDLEWARE=[
		middleware
		for middleware in settings.MIDDLEWARE
		if middleware != 'core.middleware.ProfileCompleteMiddleware'
	]
)
class PatientChartProcessFlowTests(TestCase):
	def setUp(self):
		self.doctor = User.objects.create_user(
			email='doctor-chart@test.com',
			password='DoctorPass123!',
			role='doctor',
			is_staff=True,
			is_active=True,
			first_name='Chart',
			last_name='Doctor',
		)
		_complete_staff_like_profile(self.doctor, 'DOC-CHART-001')
		self.patient = User.objects.create_user(
			email='patient-chart@test.com',
			password='PatientPass123!',
			role='patient',
			is_active=True,
			first_name='Maria',
			last_name='Chart',
		)
		self.chart = PatientChart.objects.create(
			user=self.patient,
			last_name='Chart',
			first_name='Maria',
			email_address='patient-chart@test.com',
			contact_number='09171234567',
			designation='student',
			gender='female',
		)
		self.client.force_login(self.doctor)
		self.detail_url = reverse('health_forms_services:patient_chart_detail', args=[self.chart.pk])
		self.edit_url = reverse('health_forms_services:edit_patient_chart', args=[self.chart.pk])

	def _personal_post_data(self, **overrides):
		data = {
			'section': 'personal',
			'last_name': 'Chart',
			'first_name': 'Maria',
			'middle_name': '',
			'address': '123 Campus Ave',
			'date_of_birth': '',
			'place_of_birth': '',
			'age': '20',
			'gender': 'female',
			'civil_status': 'single',
			'email_address': 'patient-chart@test.com',
			'contact_number': '09171234567',
			'telephone_number': '',
			'designation': 'student',
			'department_college_office': 'College of Nursing',
			'guardian_name': 'Parent Name',
			'guardian_contact': '09179876543',
		}
		data.update(overrides)
		return data

	def test_edit_personal_not_readonly(self):
		response = self.client.get(self.edit_url)
		self.assertEqual(response.status_code, 200)
		content = response.content.decode()
		self.assertIn('data-section-save="ajax"', content)
		self.assertNotIn('Personal information is read-only', content)
		self.assertNotRegex(
			content,
			r'<form[^>]*data-section="personal"[^>]*data-section-readonly="1"',
		)
		self.assertContains(response, 'Name &amp; Demographics')

	def test_create_form_designation_includes_guest_label(self):
		response = self.client.get(reverse('health_forms_services:create_patient_chart'))
		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Student')
		self.assertContains(response, 'Employee')
		self.assertContains(response, 'Guest')
		self.assertNotContains(response, '>Patient</option>')

	def test_edit_personal_saves(self):
		response = self.client.post(
			self.edit_url,
			self._personal_post_data(first_name='Mariana', address='456 New St'),
			HTTP_X_REQUESTED_WITH='XMLHttpRequest',
		)
		self.assertEqual(response.status_code, 200)
		payload = response.json()
		self.assertTrue(payload['success'])
		self.assertEqual(payload['section'], 'personal')
		self.chart.refresh_from_db()
		self.assertEqual(self.chart.first_name, 'Mariana')
		self.assertEqual(self.chart.address, '456 New St')

	def test_detail_shows_entry_form_and_export(self):
		response = self.client.get(self.detail_url)
		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Consultation Log')
		self.assertContains(response, 'patient-chart-entry-form')
		self.assertContains(response, 'patient-chart-entries.js')
		self.assertContains(response, 'Download .docx')
		self.assertContains(response, 'Patient Chart (F-HSS-20-0002)')
		self.assertContains(response, 'No consultation entries yet')

	def test_add_chart_entry(self):
		add_url = reverse('health_forms_services:add_chart_entry', args=[self.chart.pk])
		response = self.client.post(
			add_url,
			{
				'date_and_time': '2025-06-15T14:30',
				'findings': 'Mild headache',
				'doctors_orders': 'Rest and hydration',
			},
			HTTP_X_REQUESTED_WITH='XMLHttpRequest',
		)
		self.assertEqual(response.status_code, 200)
		payload = response.json()
		self.assertTrue(payload['success'])
		entry_data = payload['entry']
		self.assertEqual(entry_data['findings'], 'Mild headache')
		self.assertEqual(entry_data['doctors_orders'], 'Rest and hydration')
		self.assertIn('delete_url', entry_data)
		entry = PatientChartEntry.objects.get(pk=entry_data['id'])
		self.assertEqual(entry.patient_chart_id, self.chart.pk)
		self.assertEqual(entry.recorded_by_id, self.doctor.id)

	def test_add_chart_entry_requires_findings_or_orders(self):
		add_url = reverse('health_forms_services:add_chart_entry', args=[self.chart.pk])
		response = self.client.post(
			add_url,
			{'date_and_time': '2025-06-15T14:30', 'findings': '', 'doctors_orders': ''},
			HTTP_X_REQUESTED_WITH='XMLHttpRequest',
		)
		self.assertEqual(response.status_code, 400)
		payload = response.json()
		self.assertFalse(payload['success'])
		self.assertIn('__all__', payload['errors'])

	def test_add_chart_entries_back_to_back(self):
		"""Two consecutive adds should both succeed (regression for double-submit reset bug)."""
		add_url = reverse('health_forms_services:add_chart_entry', args=[self.chart.pk])
		for idx, findings in enumerate(['First visit', 'Second visit'], start=1):
			response = self.client.post(
				add_url,
				{
					'date_and_time': f'2025-06-1{idx}T10:00',
					'findings': findings,
					'doctors_orders': '',
				},
				HTTP_X_REQUESTED_WITH='XMLHttpRequest',
			)
			self.assertEqual(response.status_code, 200, msg=response.content)
			self.assertTrue(response.json()['success'])
		self.assertEqual(self.chart.entries.count(), 2)

	def test_update_chart_entry(self):
		entry = PatientChartEntry.objects.create(
			patient_chart=self.chart,
			findings='Initial findings',
			doctors_orders='Initial orders',
			recorded_by=self.doctor,
		)
		update_url = reverse(
			'health_forms_services:update_chart_entry',
			args=[self.chart.pk, entry.pk],
		)
		response = self.client.post(
			update_url,
			{
				'date_and_time': '2025-06-16T09:00',
				'findings': 'Updated findings',
				'doctors_orders': 'Updated orders',
			},
			HTTP_X_REQUESTED_WITH='XMLHttpRequest',
		)
		self.assertEqual(response.status_code, 200)
		payload = response.json()
		self.assertTrue(payload['success'])
		entry.refresh_from_db()
		self.assertEqual(entry.findings, 'Updated findings')
		self.assertEqual(entry.doctors_orders, 'Updated orders')
		self.assertIn('update_url', payload['entry'])

	def test_detail_shows_findings_and_orders_fields(self):
		response = self.client.get(self.detail_url)
		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Findings')
		self.assertContains(response, "Doctor's Orders")
		self.assertContains(response, 'Examination findings')
		self.assertContains(response, 'Medications, follow-up')

	def test_delete_chart_entry(self):
		entry = PatientChartEntry.objects.create(
			patient_chart=self.chart,
			findings='To remove',
			doctors_orders='Follow up',
			recorded_by=self.doctor,
		)
		delete_url = reverse(
			'health_forms_services:delete_chart_entry',
			args=[self.chart.pk, entry.pk],
		)
		response = self.client.post(delete_url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
		self.assertEqual(response.status_code, 200)
		self.assertTrue(response.json()['success'])
		self.assertFalse(PatientChartEntry.objects.filter(pk=entry.pk).exists())

	def test_detail_lists_existing_entries(self):
		PatientChartEntry.objects.create(
			patient_chart=self.chart,
			findings='Stable vitals',
			doctors_orders='Continue meds',
			recorded_by=self.doctor,
		)
		response = self.client.get(self.detail_url)
		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Stable vitals')
		self.assertContains(response, 'Continue meds')
		self.assertContains(response, 'id="entries-table-wrap"')


class HealthProfilePersonalInfoInstitutionalSectionTests(TestCase):
	def _institutional_field_names(self, form):
		sections = form.personal_info_sections()
		institutional = next(s for s in sections if s.get('key') == 'institutional_details')
		return [item['name'] for item in institutional['fields']]

	def test_designation_field_includes_guest_option(self):
		form = HealthProfilePersonalInfoForm()
		choice_values = [value for value, _ in form.fields['designation'].choices]
		self.assertIn('guest', choice_values)

	def test_designation_field_excludes_employee_option(self):
		form = HealthProfilePersonalInfoForm()
		choice_values = [value for value, _ in form.fields['designation'].choices]
		self.assertNotIn('employee', choice_values)

	def test_institutional_fields_for_student_designation(self):
		form = HealthProfilePersonalInfoForm(initial={'designation': 'student'})
		field_names = self._institutional_field_names(form)
		self.assertEqual(
			field_names,
			[
				'designation',
				'is_employee',
				'institution_id',
				'department_college_office',
				'course',
				'year_level',
				'position',
			],
		)

	def test_institutional_fields_for_staff_designation(self):
		form = HealthProfilePersonalInfoForm(initial={'designation': 'staff'})
		field_names = self._institutional_field_names(form)
		self.assertEqual(
			field_names,
			[
				'designation',
				'is_employee',
				'institution_id',
				'department_college_office',
				'course',
				'year_level',
				'position',
			],
		)

	def test_institutional_fields_for_doctor_designation(self):
		form = HealthProfilePersonalInfoForm(initial={'designation': 'doctor'})
		field_names = self._institutional_field_names(form)
		self.assertEqual(
			field_names,
			[
				'designation',
				'institution_id',
				'department_college_office',
				'position',
				'specialization',
				'license_number',
				'ptr_no',
			],
		)

	def test_institutional_fields_for_guest_designation(self):
		form = HealthProfilePersonalInfoForm(initial={'designation': 'guest'})
		field_names = self._institutional_field_names(form)
		self.assertEqual(field_names, ['designation'])

	def test_blank_course_and_year_fallback_to_patient_profile(self):
		from core.models import PatientProfile, User
		from health_forms_services.forms import _soft_fill_academic_fields_from_patient_profile

		patient = User.objects.create_user(
			email='academic-fallback@test.com',
			password='Pass123!',
			role='patient',
			is_active=True,
			first_name='Ana',
			last_name='Student',
		)
		profile = PatientProfile.objects.get(user=patient)
		profile.patient_id = 'P-ACAD-001'
		profile.department = 'College of Information Technology Education'
		profile.course = 'BS Information Technology'
		profile.year_level = '2nd Year'
		profile.save(update_fields=['patient_id', 'department', 'course', 'year_level'])
		self.assertEqual(
			PatientProfile.objects.get(user=patient).course,
			'BS Information Technology',
		)

		health_form = HealthProfileForm.objects.create(
			user=patient,
			status=HealthProfileForm.Status.INCOMPLETE,
			first_name='Ana',
			last_name='Student',
			designation='student',
			department_college_office='College of Information Technology Education',
			institution_id='P-ACAD-001',
			course='',
			year_level='',
		)
		_soft_fill_academic_fields_from_patient_profile(health_form)
		self.assertEqual(health_form.course, 'BS Information Technology')
		self.assertEqual(health_form.year_level, '2nd Year')

		form = HealthProfilePersonalInfoForm(instance=health_form)
		self.assertEqual(form['course'].value(), 'BS Information Technology')
		self.assertEqual(form['year_level'].value(), '2nd Year')
		self.assertEqual(
			form['department_college_office'].value(),
			'College of Information Technology Education',
		)

	def test_dental_and_chart_blank_department_fallback_to_patient_profile(self):
		from core.models import PatientProfile, User

		patient = User.objects.create_user(
			email='dept-fallback@test.com',
			password='Pass123!',
			role='patient',
			is_active=True,
			first_name='Ben',
			last_name='Student',
		)
		profile = PatientProfile.objects.get(user=patient)
		profile.department = 'College of Nursing'
		profile.save(update_fields=['department'])

		dental = DentalHealthForm(
			user=patient,
			status=DentalHealthForm.Status.PENDING,
			first_name='Ben',
			last_name='Student',
			department_college_office='',
		)
		chart = PatientChart(
			user=patient,
			status=PatientChart.Status.PENDING,
			first_name='Ben',
			last_name='Student',
			department_college_office='',
		)
		services = DentalServicesRequest(
			user=patient,
			status=DentalServicesRequest.Status.PENDING,
			first_name='Ben',
			last_name='Student',
			department='',
		)

		dental_form = DentalHealthPersonalInfoForm(instance=dental)
		chart_form = PatientChartPersonalInfoForm(instance=chart)
		services_form = DentalServicesPersonalInfoForm(instance=services)

		self.assertEqual(dental_form['department_college_office'].value(), 'College of Nursing')
		self.assertEqual(chart_form['department_college_office'].value(), 'College of Nursing')
		self.assertEqual(services_form['department'].value(), 'College of Nursing')

	def test_guest_clean_clears_institutional_fields(self):
		form = HealthProfilePersonalInfoForm(data={
			'last_name': 'Guest',
			'first_name': 'User',
			'date_of_birth': '2000-01-01',
			'gender': 'female',
			'designation': 'guest',
			'department_college_office': 'College of Nursing',
			'mobile_number': '+639171234567',
			'email_address': 'guest@example.com',
			'institution_id': '24-0001',
			'course': 'BSN',
			'year_level': '4th Year',
			'position': 'Nurse',
			'specialization': 'Internal Medicine',
			'license_number': 'PRC-123',
			'ptr_no': 'PTR-456',
		})
		self.assertTrue(form.is_valid(), msg=form.errors.as_text())
		self.assertEqual(form.cleaned_data['department_college_office'], '')
		self.assertEqual(form.cleaned_data['institution_id'], '')
		self.assertEqual(form.cleaned_data['course'], '')
		self.assertEqual(form.cleaned_data['year_level'], '')
		self.assertEqual(form.cleaned_data['position'], '')
		self.assertEqual(form.cleaned_data['specialization'], '')
		self.assertEqual(form.cleaned_data['license_number'], '')
		self.assertEqual(form.cleaned_data['ptr_no'], '')

	def test_personal_info_form_readonly_disables_fields(self):
		form = HealthProfilePersonalInfoForm(readonly=True)
		for name, field in form.fields.items():
			self.assertTrue(field.disabled, msg=name)


class DentalAndChartGuestDesignationTests(TestCase):
	def test_dental_personal_sections_for_guest_hide_department(self):
		form = DentalHealthPersonalInfoForm(initial={'designation': 'guest'})
		sections = form.dental_personal_sections()
		institution = next(s for s in sections if s.get('label') == 'Institution')
		field_names = [item['name'] for item in institution['fields']]
		self.assertEqual(field_names, ['designation'])

	def test_dental_personal_clean_clears_department_for_guest(self):
		form = DentalHealthPersonalInfoForm(data={
			'last_name': 'Guest',
			'first_name': 'Dental',
			'designation': 'guest',
			'department_college_office': 'College of Nursing',
		})
		self.assertTrue(form.is_valid(), msg=form.errors.as_text())
		self.assertEqual(form.cleaned_data['department_college_office'], '')

	def test_patient_chart_sections_for_guest_hide_department(self):
		form = PatientChartPersonalInfoForm(initial={'designation': 'guest'})
		sections = form.personal_info_sections()
		designation_section = next(s for s in sections if s.get('label') == 'Designation')
		field_names = [item['name'] for item in designation_section['fields']]
		self.assertEqual(field_names, ['designation'])

	def test_patient_chart_clean_clears_department_for_guest(self):
		form = PatientChartPersonalInfoForm(data={
			'last_name': 'Chart',
			'first_name': 'Guest',
			'designation': 'guest',
			'department_college_office': 'College of Nursing',
		})
		self.assertTrue(form.is_valid(), msg=form.errors.as_text())
		self.assertEqual(form.cleaned_data['department_college_office'], '')


@override_settings(
	MIDDLEWARE=[
		middleware
		for middleware in settings.MIDDLEWARE
		if middleware != 'core.middleware.ProfileCompleteMiddleware'
	]
)
class PrescriptionBodyFormatTests(TestCase):
	def setUp(self):
		self.doctor = User.objects.create_user(
			email='rx-detail@test.com',
			password='DoctorPass123!',
			role='doctor',
			is_staff=True,
			is_active=True,
			first_name='Rx',
			last_name='Doctor',
		)
		_complete_staff_like_profile(self.doctor, 'DOC-RX-001')
		self.client.force_login(self.doctor)

	def test_split_prescription_body_parses_section_markers(self):
		body = join_prescription_body('tonsil', 'Paracetamol 500 mg', 'Take after meals')
		sections = split_prescription_body(body)
		self.assertEqual(sections['diagnosis'], 'tonsil')
		self.assertEqual(sections['medications'], 'Paracetamol 500 mg')
		self.assertEqual(sections['instructions'], 'Take after meals')

	def test_split_prescription_body_handles_legacy_diagnosis_prefix(self):
		sections = split_prescription_body('Diagnosis: tonsillitis\nMedications: Amoxicillin')
		self.assertEqual(sections['diagnosis'], 'tonsillitis')
		self.assertEqual(sections['medications'], '')
		self.assertEqual(sections['instructions'], '')

	def test_prescription_detail_renders_clinical_notes_without_markers(self):
		prescription = Prescription.objects.create(
			user=self.doctor,
			patient_name='Test Patient',
			prescription_body=join_prescription_body('tonsil', '', ''),
		)
		response = self.client.get(
			reverse('health_forms_services:prescription_detail', args=[prescription.pk]),
		)
		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Clinical Notes')
		self.assertContains(response, 'Diagnosis / Impression')
		self.assertContains(response, 'tonsil')
		self.assertNotContains(response, '___DIAGNOSIS___')

	def test_add_prescription_item_persists_and_shows_on_detail(self):
		prescription = Prescription.objects.create(
			user=self.doctor,
			patient_name='Test Patient',
		)
		add_url = reverse('health_forms_services:add_prescription_item', args=[prescription.pk])
		response = self.client.post(
			add_url,
			{
				'medication_name': 'Amoxicillin',
				'dosage': '500 mg',
				'frequency': '3× daily',
				'duration': '7 days',
				'quantity': '#21',
				'instructions': 'Take after meals',
			},
			HTTP_X_REQUESTED_WITH='XMLHttpRequest',
		)
		self.assertEqual(response.status_code, 200)
		payload = response.json()
		self.assertTrue(payload['success'])
		self.assertEqual(PrescriptionItem.objects.filter(prescription=prescription).count(), 1)

		detail_response = self.client.get(
			reverse('health_forms_services:prescription_detail', args=[prescription.pk]),
		)
		self.assertEqual(detail_response.status_code, 200)
		self.assertContains(detail_response, 'Amoxicillin')
		self.assertContains(detail_response, '500 mg')

	def test_edit_prescription_shows_existing_items(self):
		prescription = Prescription.objects.create(
			user=self.doctor,
			patient_name='Test Patient',
		)
		PrescriptionItem.objects.create(
			prescription=prescription,
			medication_name='Paracetamol',
			dosage='500 mg',
		)
		response = self.client.get(
			reverse('health_forms_services:edit_prescription', args=[prescription.pk]),
		)
		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Paracetamol')
		self.assertContains(response, '500 mg')
		self.assertContains(response, 'prescription-items-form.js')


@override_settings(
	MIDDLEWARE=[
		middleware
		for middleware in settings.MIDDLEWARE
		if middleware != 'core.middleware.ProfileCompleteMiddleware'
	],
	EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
	STORAGES={
		'default': {
			'BACKEND': 'django.core.files.storage.FileSystemStorage',
		},
		'staticfiles': {
			'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
		},
	},
)
class HealthProfilePatientWorkflowTests(TestCase):
	def setUp(self):
		from core.doctor_access import ALL_MODULE_KEYS

		self.doctor = User.objects.create_user(
			email='doctor-hp-workflow@test.com',
			password='DoctorPass123!',
			role='doctor',
			is_staff=True,
			is_active=True,
			first_name='Workflow',
			last_name='Doctor',
		)
		_complete_staff_like_profile(self.doctor, 'DOC-HP-WF-001')
		doc_profile = self.doctor.staff_profile
		doc_profile.allowed_clinical_modules = list(ALL_MODULE_KEYS)
		doc_profile.save(update_fields=['allowed_clinical_modules'])

		self.patient = User.objects.create_user(
			email='patient-hp-workflow@test.com',
			password='PatientPass123!',
			role='patient',
			is_active=True,
			first_name='Cara',
			last_name='Patient',
		)
		profile, _ = PatientProfile.objects.get_or_create(user=self.patient)
		profile.patient_id = 'P-HP-2001'
		profile.gender = 'female'
		profile.civil_status = 'single'
		profile.address = '456 Clinic Rd'
		profile.phone = '+639171111111'
		profile.course = 'BSN'
		profile.department = 'College of Nursing'
		profile.date_of_birth = timezone.now().date().replace(year=2001, month=5, day=10)
		profile.age = 24
		profile.save()
		self.patient.__dict__.pop('patient_profile', None)
		self.patient._state.fields_cache.pop('patient_profile', None)
		self.other_patient = User.objects.create_user(
			email='other-hp-workflow@test.com',
			password='PatientPass123!',
			role='patient',
			is_active=True,
			first_name='Other',
			last_name='Person',
		)
		other_profile, _ = PatientProfile.objects.get_or_create(user=self.other_patient)
		other_profile.patient_id = 'P-HP-2002'
		other_profile.save(update_fields=['patient_id'])

	def _login_patient(self):
		self.client.force_login(self.patient)

	def _login_doctor(self):
		self.client.force_login(self.doctor)

	def _fill_required_personal(self, form_obj):
		form_obj.last_name = 'Patient'
		form_obj.first_name = 'Cara'
		form_obj.date_of_birth = timezone.now().date().replace(year=2001, month=5, day=10)
		form_obj.gender = 'female'
		form_obj.designation = 'student'
		form_obj.department_college_office = 'College of Nursing'
		form_obj.mobile_number = '+639171111111'
		form_obj.email_address = self.patient.email
		form_obj.save()

	def test_patient_can_open_health_profile_list_scoped_to_self(self):
		own = HealthProfileForm.objects.create(
			user=self.patient,
			status=HealthProfileForm.Status.INCOMPLETE,
			first_name='Cara',
			last_name='Patient',
		)
		HealthProfileForm.objects.create(
			user=self.other_patient,
			status=HealthProfileForm.Status.INCOMPLETE,
			first_name='Other',
			last_name='Person',
		)
		self._login_patient()
		response = self.client.get(reverse('health_forms_services:forms_list'))
		self.assertEqual(response.status_code, 200)
		self.assertNotContains(response, 'Request Health Profile Form')
		self.assertNotContains(response, 'Your health profile forms')
		forms = list(response.context['forms'])
		self.assertEqual(len(forms), 1)
		self.assertEqual(forms[0].pk, own.pk)

	def test_patient_navbar_shows_health_profile_without_module_grant(self):
		from django.template import Context, Template
		from django.template.loader import render_to_string

		self._login_patient()
		html = render_to_string(
			'core/partials/_nav_health_forms_desktop.html',
			{
				'user': self.patient,
				'request': type('R', (), {'user': self.patient})(),
				'hide_removed_app_links': False,
				'clinical_nav': {'show_health_forms': False},
				'doctor_nav': {'show_health_forms': False},
				'nav_active': {'health_forms': False},
				'include_document_request_link': False,
			},
		)
		self.assertIn('Health Profile Forms', html)
		self.assertNotIn('Dental Health Forms', html)
		self.assertNotIn('Patient Charts', html)
		self.assertNotIn('Prescriptions', html)

	def test_patient_request_creates_incomplete_draft_with_prefill(self):
		from health_forms_services.views._fbvs import _patient_profile_prefill_payload

		self.assertEqual(self.patient.patient_profile.department, 'College of Nursing')
		payload = _patient_profile_prefill_payload(self.patient)
		self.assertEqual(payload.get('department_college_office'), 'College of Nursing')

		self._login_patient()
		response = self.client.get(reverse('health_forms_services:request_health_profile'))
		self.assertEqual(response.status_code, 302)
		created = HealthProfileForm.objects.get(user=self.patient)
		self.assertEqual(created.status, HealthProfileForm.Status.INCOMPLETE)
		self.assertEqual(created.first_name, 'Cara')
		self.assertEqual(created.last_name, 'Patient')
		self.assertEqual(created.department_college_office, 'College of Nursing')
		self.assertEqual(created.course, 'BSN')
		self.assertEqual(created.mobile_number, '+639171111111')

	def test_patient_edit_history_only_and_cannot_post_clinical(self):
		form_obj = HealthProfileForm.objects.create(
			user=self.patient,
			status=HealthProfileForm.Status.INCOMPLETE,
		)
		self._login_patient()
		response = self.client.get(reverse('health_forms_services:edit_form', args=[form_obj.pk]))
		self.assertEqual(response.status_code, 200)
		tab_keys = [t['key'] for t in response.context['tabs']]
		self.assertEqual(tab_keys, ['personal', 'medical'])
		self.assertFalse(response.context['personal_readonly'])

		blocked = self.client.post(
			reverse('health_forms_services:edit_form', args=[form_obj.pk]),
			{'section': 'physical', 'blood_pressure': '120/80'},
			HTTP_X_REQUESTED_WITH='XMLHttpRequest',
		)
		self.assertEqual(blocked.status_code, 403)

	def test_patient_submit_for_review_and_locked_after(self):
		form_obj = HealthProfileForm.objects.create(
			user=self.patient,
			status=HealthProfileForm.Status.INCOMPLETE,
		)
		self._fill_required_personal(form_obj)
		self._login_patient()

		missing = HealthProfileForm.objects.create(
			user=self.patient,
			status=HealthProfileForm.Status.INCOMPLETE,
			first_name='Incomplete',
		)
		bad = self.client.post(reverse('health_forms_services:submit_for_review', args=[missing.pk]))
		self.assertIn(bad.status_code, (200, 302))
		missing.refresh_from_db()
		self.assertEqual(missing.status, HealthProfileForm.Status.INCOMPLETE)
		if bad.status_code == 200:
			self.assertTrue(
				b'required before submitting for review' in bad.content.lower()
				or b'last name' in bad.content.lower()
				or bad.context is not None,
			)

		ok = self.client.post(reverse('health_forms_services:submit_for_review', args=[form_obj.pk]))
		self.assertEqual(ok.status_code, 302)
		form_obj.refresh_from_db()
		self.assertEqual(form_obj.status, HealthProfileForm.Status.PENDING)

		from core.models import Notification

		clinician_notifs = Notification.objects.filter(
			user=self.doctor,
			transaction_type='health_form_submitted',
			related_id=form_obj.pk,
		)
		self.assertEqual(clinician_notifs.count(), 1)
		self.assertIn('submitted', clinician_notifs.first().title.lower())

		edit = self.client.get(reverse('health_forms_services:edit_form', args=[form_obj.pk]))
		self.assertEqual(edit.status_code, 302)
		post_blocked = self.client.post(
			reverse('health_forms_services:edit_form', args=[form_obj.pk]),
			{'section': 'personal', 'first_name': 'Hacked'},
			HTTP_X_REQUESTED_WITH='XMLHttpRequest',
		)
		self.assertEqual(post_blocked.status_code, 403)

	def test_patient_cancel_draft_and_delete_incomplete(self):
		draft = HealthProfileForm.objects.create(
			user=self.patient,
			status=HealthProfileForm.Status.INCOMPLETE,
			first_name='Cara',
			last_name='Patient',
		)
		self._login_patient()

		edit = self.client.get(reverse('health_forms_services:edit_form', args=[draft.pk]))
		self.assertEqual(edit.status_code, 200)
		self.assertContains(edit, 'Cancel draft')
		self.assertContains(edit, 'open-modal')
		self.assertContains(edit, reverse('health_forms_services:delete_form', args=[draft.pk]))
		self.assertNotContains(edit, reverse('health_forms_services:cancel_draft', args=[draft.pk]))

		deleted = self.client.post(reverse('health_forms_services:delete_form', args=[draft.pk]))
		self.assertEqual(deleted.status_code, 302)
		self.assertFalse(HealthProfileForm.objects.filter(pk=draft.pk).exists())

	def test_patient_detail_shows_cancel_and_delete_for_draft(self):
		draft = HealthProfileForm.objects.create(
			user=self.patient,
			status=HealthProfileForm.Status.INCOMPLETE,
			first_name='Cara',
			last_name='Patient',
		)
		self._login_patient()
		detail = self.client.get(reverse('health_forms_services:form_detail', args=[draft.pk]))
		self.assertEqual(detail.status_code, 200)
		self.assertContains(detail, 'Cancel draft')
		self.assertContains(detail, 'open-modal')
		self.assertContains(detail, reverse('health_forms_services:delete_form', args=[draft.pk]))
		self.assertNotContains(detail, reverse('health_forms_services:cancel_draft', args=[draft.pk]))

	def test_patient_can_cancel_pending_submission(self):
		form_obj = HealthProfileForm.objects.create(
			user=self.patient,
			status=HealthProfileForm.Status.PENDING,
			first_name='Cara',
			last_name='Patient',
		)
		self._login_patient()
		detail = self.client.get(reverse('health_forms_services:form_detail', args=[form_obj.pk]))
		self.assertEqual(detail.status_code, 200)
		self.assertContains(detail, 'Cancel submission')
		self.assertContains(detail, reverse('health_forms_services:delete_form', args=[form_obj.pk]))

		resp = self.client.post(reverse('health_forms_services:delete_form', args=[form_obj.pk]))
		self.assertEqual(resp.status_code, 302)
		self.assertFalse(HealthProfileForm.objects.filter(pk=form_obj.pk).exists())

	def test_doctor_edits_clinical_on_pending_and_completes_review(self):
		form_obj = HealthProfileForm.objects.create(
			user=self.patient,
			status=HealthProfileForm.Status.PENDING,
			first_name='Cara',
			last_name='Patient',
		)
		self._login_doctor()
		response = self.client.get(reverse('health_forms_services:edit_form', args=[form_obj.pk]))
		self.assertEqual(response.status_code, 200)
		self.assertTrue(response.context['personal_readonly'])
		self.assertIn('physical', response.context['editable_sections'])
		self.assertNotIn('personal', response.context['editable_sections'])

		save = self.client.post(
			reverse('health_forms_services:edit_form', args=[form_obj.pk]),
			{'section': 'physical', 'blood_pressure': '110/70', 'heart_rate': '72'},
			follow=True,
		)
		self.assertEqual(save.status_code, 200)
		form_obj.refresh_from_db()
		self.assertEqual(form_obj.blood_pressure, '110/70')

		review = self.client.post(
			reverse('health_forms_services:review_form', args=[form_obj.pk]),
			{'status': 'completed', 'review_notes': 'Cleared'},
		)
		self.assertEqual(review.status_code, 302)
		form_obj.refresh_from_db()
		self.assertEqual(form_obj.status, HealthProfileForm.Status.COMPLETED)

		from core.models import Notification

		patient_notifs = Notification.objects.filter(
			user=self.patient,
			transaction_type='health_form_completed',
			related_id=form_obj.pk,
		)
		self.assertEqual(patient_notifs.count(), 1)
		self.assertIn('completed', patient_notifs.first().title.lower())

	def test_reject_returns_to_incomplete_for_patient_revision(self):
		form_obj = HealthProfileForm.objects.create(
			user=self.patient,
			status=HealthProfileForm.Status.PENDING,
			first_name='Cara',
			last_name='Patient',
		)
		self._login_doctor()
		self.client.post(
			reverse('health_forms_services:review_form', args=[form_obj.pk]),
			{'status': 'rejected', 'review_notes': 'Please update history'},
		)
		form_obj.refresh_from_db()
		self.assertEqual(form_obj.status, HealthProfileForm.Status.INCOMPLETE)
		self.assertIn('Please update history', form_obj.review_notes)

		self._login_patient()
		edit = self.client.get(reverse('health_forms_services:edit_form', args=[form_obj.pk]))
		self.assertEqual(edit.status_code, 200)
		self.assertIn('personal', edit.context['editable_sections'])

	def test_staff_manual_entry_starts_incomplete(self):
		self._login_doctor()
		response = self.client.post(
			reverse('health_forms_services:manual_entry'),
			{
				'selected_user_id': str(self.patient.id),
				'last_name': 'Patient',
				'first_name': 'Cara',
				'middle_name': '',
				'permanent_address': '456 Clinic Rd',
				'zip_code': '',
				'current_address': '456 Clinic Rd',
				'religion': '',
				'civil_status': 'single',
				'place_of_birth': 'Manila',
				'date_of_birth': '2001-05-10',
				'citizenship': 'Filipino',
				'age': '24',
				'gender': 'female',
				'email_address': self.patient.email,
				'mobile_number': '+639171111111',
				'telephone_number': '',
				'designation': 'student',
				'institution_id': 'P-HP-2001',
				'department_college_office': 'College of Nursing',
				'course': 'BSN',
				'year_level': '',
				'position': '',
				'specialization': '',
				'license_number': '',
				'ptr_no': '',
				'blood_type': '',
				'medical_conditions': '',
				'guardian_name': '',
				'guardian_contact': '',
			},
			follow=True,
		)
		self.assertEqual(response.status_code, 200)
		created = HealthProfileForm.objects.filter(user=self.patient).latest('created_at')
		self.assertEqual(created.status, HealthProfileForm.Status.INCOMPLETE)

	def test_staff_manual_entry_notifies_patient_and_emails_edit_link(self):
		from django.core import mail
		from core.doctor_access import ALL_MODULE_KEYS
		from core.models import ClinicSettings, Notification, UserPreferences
		from core.settings_service import invalidate_settings_cache
		from core.utils import resolve_notification_url

		ClinicSettings.load()
		ClinicSettings.objects.filter(pk=ClinicSettings.SINGLETON_PK).update(
			enable_email_notifications=True,
		)
		invalidate_settings_cache()

		prefs, _ = UserPreferences.objects.get_or_create(user=self.patient)
		prefs.in_app_notifications = True
		prefs.email_notifications = True
		prefs.save(update_fields=['in_app_notifications', 'email_notifications'])

		# Ensure module grants survive any settings-cache side effects before the POST.
		doc_profile = self.doctor.staff_profile
		doc_profile.allowed_clinical_modules = list(ALL_MODULE_KEYS)
		doc_profile.save(update_fields=['allowed_clinical_modules'])

		HealthProfileForm.objects.filter(user=self.patient).delete()
		self._login_doctor()
		response = self.client.post(
			reverse('health_forms_services:manual_entry'),
			{
				'selected_user_id': str(self.patient.id),
				'last_name': 'Patient',
				'first_name': 'Cara',
				'middle_name': '',
				'permanent_address': '456 Clinic Rd',
				'zip_code': '',
				'current_address': '456 Clinic Rd',
				'religion': '',
				'civil_status': 'single',
				'place_of_birth': 'Manila',
				'date_of_birth': '2001-05-10',
				'citizenship': 'Filipino',
				'age': '24',
				'gender': 'female',
				'email_address': self.patient.email,
				'mobile_number': '+639171111111',
				'telephone_number': '',
				'designation': 'student',
				'institution_id': 'P-HP-2001',
				'department_college_office': 'College of Nursing',
				'course': 'BS Nursing',
				'year_level': '',
				'position': '',
				'specialization': '',
				'license_number': '',
				'ptr_no': '',
				'blood_type': '',
				'allergies': '',
				'medical_conditions': '',
				'guardian_name': '',
				'guardian_contact': '',
			},
		)
		errors = ''
		if response.status_code == 200 and getattr(response, 'context', None):
			personal_form = response.context.get('personal_form')
			if personal_form is not None:
				errors = str(personal_form.errors)
		self.assertEqual(
			response.status_code,
			302,
			msg=f'expected redirect after create; status={response.status_code} loc={getattr(response, "url", None)!r} errors={errors}',
		)
		self.assertTrue(
			HealthProfileForm.objects.filter(user=self.patient).exists(),
			msg=f'redirect to {response.url!r} but no form created; all forms={list(HealthProfileForm.objects.values_list("pk","user_id","status"))}',
		)
		created = HealthProfileForm.objects.filter(user=self.patient).latest('created_at')
		self.assertEqual(created.status, HealthProfileForm.Status.INCOMPLETE)
		notif = Notification.objects.filter(
			user=self.patient,
			transaction_type='health_form_incomplete',
			related_id=created.pk,
		).first()
		self.assertIsNotNone(
			notif,
			msg=list(Notification.objects.filter(user=self.patient).values_list('title', 'transaction_type', 'related_id')),
		)
		self.assertEqual(
			resolve_notification_url(notif),
			reverse('health_forms_services:edit_form', args=[created.pk]),
		)
		self.assertEqual(len(mail.outbox), 1)
		self.assertEqual(mail.outbox[0].to, [self.patient.email])
		self.assertIn(f'/health-forms/{created.pk}/edit/', mail.outbox[0].body)
		self.assertNotIn('/guest/health-form/', mail.outbox[0].body)

	def test_staff_manual_entry_guest_sends_magic_link_only(self):
		from django.core import mail
		from core.doctor_access import ALL_MODULE_KEYS
		from core.guest_auth import is_guest_user
		from core.models import ClinicSettings, Notification
		from core.settings_service import invalidate_settings_cache

		ClinicSettings.load()
		ClinicSettings.objects.filter(pk=ClinicSettings.SINGLETON_PK).update(
			enable_email_notifications=True,
		)
		invalidate_settings_cache()

		doc_profile = self.doctor.staff_profile
		doc_profile.allowed_clinical_modules = list(ALL_MODULE_KEYS)
		doc_profile.save(update_fields=['allowed_clinical_modules'])

		self._login_doctor()
		response = self.client.post(
			reverse('health_forms_services:manual_entry'),
			{
				'register_guest': '1',
				'last_name': 'Guest',
				'first_name': 'Walkin',
				'middle_name': '',
				'permanent_address': '1 Guest St',
				'zip_code': '',
				'current_address': '1 Guest St',
				'religion': '',
				'civil_status': 'single',
				'place_of_birth': 'Manila',
				'date_of_birth': '1999-01-01',
				'citizenship': 'Filipino',
				'age': '26',
				'gender': 'female',
				'email_address': 'guest-hf-notify@test.com',
				'mobile_number': '+639171111222',
				'telephone_number': '',
				'designation': 'guest',
				'institution_id': '',
				'department_college_office': '',
				'course': '',
				'year_level': '',
				'position': '',
				'specialization': '',
				'license_number': '',
				'ptr_no': '',
				'blood_type': '',
				'allergies': '',
				'medical_conditions': '',
				'guardian_name': '',
				'guardian_contact': '',
			},
		)
		self.assertEqual(response.status_code, 302, msg=getattr(response, 'url', None))
		created = HealthProfileForm.objects.latest('created_at')
		self.assertTrue(is_guest_user(created.user))
		self.assertEqual(created.status, HealthProfileForm.Status.INCOMPLETE)
		self.assertFalse(
			Notification.objects.filter(
				user=created.user,
				transaction_type='health_form_incomplete',
			).exists()
		)
		self.assertEqual(len(mail.outbox), 1)
		self.assertEqual(mail.outbox[0].to, ['guest-hf-notify@test.com'])
		self.assertIn('/guest/health-form/', mail.outbox[0].body)
		self.assertNotIn(f'/health-forms/{created.pk}/edit/', mail.outbox[0].body)

	def test_invite_guest_health_profile_creates_draft_and_emails_link(self):
		from django.core import mail
		from core.doctor_access import ALL_MODULE_KEYS
		from core.guest_auth import is_guest_user
		from core.models import ClinicSettings
		from core.settings_service import invalidate_settings_cache

		ClinicSettings.load()
		ClinicSettings.objects.filter(pk=ClinicSettings.SINGLETON_PK).update(
			enable_email_notifications=True,
		)
		invalidate_settings_cache()

		doc_profile = self.doctor.staff_profile
		doc_profile.allowed_clinical_modules = list(ALL_MODULE_KEYS)
		doc_profile.save(update_fields=['allowed_clinical_modules'])

		self._login_doctor()
		response = self.client.post(
			reverse('health_forms_services:invite_guest_health_profile'),
			{
				'first_name': 'Invited',
				'last_name': 'Guest',
				'contact_email': 'invite-guest@test.com',
				'mobile_number': '+639171234567',
			},
		)
		self.assertEqual(response.status_code, 302, msg=getattr(response, 'url', None))
		created = HealthProfileForm.objects.latest('created_at')
		self.assertTrue(is_guest_user(created.user))
		self.assertEqual(created.status, HealthProfileForm.Status.INCOMPLETE)
		self.assertEqual(created.designation, 'guest')
		self.assertEqual(created.email_address, 'invite-guest@test.com')
		self.assertEqual(created.first_name, 'Invited')
		self.assertFalse(created.department_college_office)
		self.assertEqual(len(mail.outbox), 1)
		self.assertEqual(mail.outbox[0].to, ['invite-guest@test.com'])
		self.assertIn('/guest/health-form/', mail.outbox[0].body)

	def test_resend_guest_health_form_link(self):
		from django.core import mail
		from core.doctor_access import ALL_MODULE_KEYS
		from core.guest_auth import create_guest_user
		from core.models import ClinicSettings
		from core.settings_service import invalidate_settings_cache

		ClinicSettings.load()
		ClinicSettings.objects.filter(pk=ClinicSettings.SINGLETON_PK).update(
			enable_email_notifications=True,
		)
		invalidate_settings_cache()

		doc_profile = self.doctor.staff_profile
		doc_profile.allowed_clinical_modules = list(ALL_MODULE_KEYS)
		doc_profile.save(update_fields=['allowed_clinical_modules'])

		guest = create_guest_user(
			first_name='Resend',
			last_name='Guest',
			contact_email='resend-guest@test.com',
		)
		health_form = HealthProfileForm.objects.create(
			user=guest,
			status=HealthProfileForm.Status.INCOMPLETE,
			designation='guest',
			first_name='Resend',
			last_name='Guest',
			email_address='resend-guest@test.com',
		)

		self._login_doctor()
		response = self.client.post(
			reverse('health_forms_services:resend_guest_health_form_link', args=[health_form.pk]),
		)
		self.assertEqual(response.status_code, 302)
		self.assertEqual(len(mail.outbox), 1)
		self.assertEqual(mail.outbox[0].to, ['resend-guest@test.com'])
		self.assertIn('/guest/health-form/', mail.outbox[0].body)

		detail = self.client.get(reverse('health_forms_services:form_detail', args=[health_form.pk]))
		self.assertEqual(detail.status_code, 200)
		self.assertContains(detail, 'Resend link')

	def test_patient_dashboard_lists_incomplete_health_forms(self):
		HealthProfileForm.objects.filter(user=self.patient).delete()
		form_obj = HealthProfileForm.objects.create(
			user=self.patient,
			status=HealthProfileForm.Status.INCOMPLETE,
			first_name='Cara',
			last_name='Patient',
		)
		self._login_patient()
		response = self.client.get(reverse('core:dashboard'))
		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.context['pending_health_forms_count'], 1)
		self.assertEqual(list(response.context['pending_health_forms'])[0].pk, form_obj.pk)
		self.assertContains(response, 'Forms to complete')
		self.assertContains(response, 'Action needed')
		self.assertContains(response, reverse('health_forms_services:edit_form', args=[form_obj.pk]))


class HealthProfileEditableSectionsTests(TestCase):
	def setUp(self):
		self.patient = User.objects.create_user(
			email='patient-hp-perms@test.com',
			password='PatientPass123!',
			role='patient',
			is_active=True,
		)
		self.doctor = User.objects.create_user(
			email='doctor-hp-perms@test.com',
			password='DoctorPass123!',
			role='doctor',
			is_staff=True,
			is_active=True,
		)
		_complete_staff_like_profile(self.doctor, 'DOC-HP-PERM-001')
		self.form = HealthProfileForm.objects.create(
			user=self.patient,
			status=HealthProfileForm.Status.INCOMPLETE,
		)

	def test_editable_sections_matrix(self):
		from health_forms_services.services import editable_sections

		self.assertEqual(
			editable_sections(self.patient, self.form),
			frozenset({'personal', 'medical'}),
		)
		self.assertEqual(
			editable_sections(self.doctor, self.form),
			frozenset({'personal', 'medical', 'physical', 'diagnostic', 'clinical'}),
		)

		self.form.status = HealthProfileForm.Status.PENDING
		self.form.save(update_fields=['status'])
		self.assertEqual(editable_sections(self.patient, self.form), frozenset())
		self.assertEqual(
			editable_sections(self.doctor, self.form),
			frozenset({'physical', 'diagnostic', 'clinical'}),
		)

		self.form.status = HealthProfileForm.Status.COMPLETED
		self.form.save(update_fields=['status'])
		self.assertEqual(editable_sections(self.patient, self.form), frozenset())
		self.assertEqual(editable_sections(self.doctor, self.form), frozenset())
