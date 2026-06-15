from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse

from core.models import PatientProfile, StaffProfile, User
from health_forms_services.forms import DIAGNOSTIC_TEST_TRIPLETS, IMMUNIZATION_FLAG_DATE_PAIRS
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
			self._personal_post_data(first_name='Janet'),
			HTTP_X_REQUESTED_WITH='XMLHttpRequest',
		)
		self.assertEqual(response.status_code, 200)
		payload = response.json()
		self.assertTrue(payload['success'])
		self.assertEqual(payload['section'], 'personal')
		self.health_form.refresh_from_db()
		self.assertEqual(self.health_form.first_name, 'Janet')

	def test_ajax_invalid_section_returns_field_errors(self):
		response = self.client.post(
			self.edit_url,
			self._personal_post_data(mobile_number='invalid'),
			HTTP_X_REQUESTED_WITH='XMLHttpRequest',
		)
		self.assertEqual(response.status_code, 400)
		payload = response.json()
		self.assertFalse(payload['success'])
		self.assertIn('mobile_number', payload['errors'])

	def test_non_ajax_save_redirects_to_edit_with_section(self):
		response = self.client.post(
			self.edit_url,
			self._personal_post_data(first_name='Janice'),
		)
		self.assertRedirects(
			response,
			f'{self.edit_url}?section=personal',
			fetch_redirect_response=False,
		)
		self.health_form.refresh_from_db()
		self.assertEqual(self.health_form.first_name, 'Janice')

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
		self.assertEqual(response.status_code, 200, response.content)
		self.assertTrue(response.json()['success'])
		self.health_form.refresh_from_db()
		self.assertEqual(self.health_form.middle_name, 'Marie')
		self.assertEqual(self.health_form.permanent_address, '123 Main St, Manila')
		self.assertEqual(self.health_form.zip_code, '1000')
		self.assertEqual(self.health_form.telephone_number, '+639181112233')
		self.assertEqual(self.health_form.guardian_contact, '+639191112233')
		self.assertEqual(self.health_form.course, 'BS Nursing')

	def test_personal_phone_fields_reject_invalid_format(self):
		for field in ('mobile_number', 'telephone_number', 'guardian_contact'):
			with self.subTest(field=field):
				response = self._ajax_save(self._personal_post_data(**{field: '09171234567'}))
				self.assertEqual(response.status_code, 400)
				self.assertIn(field, response.json()['errors'])

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
			(self._personal_post_data(middle_name='Seq'), 'middle_name', 'Seq'),
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
		# Earlier section data should remain after later saves
		self.assertEqual(self.health_form.middle_name, 'Seq')
		self.assertEqual(self.health_form.allergies, 'Seq allergy')
