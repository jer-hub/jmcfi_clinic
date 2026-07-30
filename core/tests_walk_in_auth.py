"""Tests for staff-created walk-in guests (no public guest login)."""

import json
from datetime import date

from django.test import Client, TestCase
from django.urls import reverse

from core.doctor_access import MODULE_MEDICAL_RECORDS
from core.forms import StudentProfileForm
from core.models import PatientProfile, User
from core.tests import _complete_staff_like_profile
from core.utils import get_missing_profile_fields, is_profile_complete
from core.walk_in_auth import create_walk_in_user, is_walk_in_user


class WalkInAuthTests(TestCase):
	def test_create_walk_in_user(self):
		user = create_walk_in_user()
		self.assertEqual(user.role, 'patient')
		self.assertTrue(user.email.endswith('@walkin.local'))
		self.assertFalse(user.has_usable_password())
		self.assertTrue(is_walk_in_user(user))
		profile = user.patient_profile
		self.assertTrue(profile.patient_id.startswith('WI-'))
		field_names = {f.name for f in PatientProfile._meta.fields}
		self.assertNotIn('patient_category', field_names)

	def test_create_walk_in_user_custom_names(self):
		user = create_walk_in_user(first_name='Ana', last_name='Reyes', phone='+639171234567')
		self.assertEqual(user.first_name, 'Ana')
		self.assertEqual(user.last_name, 'Reyes')
		self.assertEqual(user.patient_profile.phone, '+639171234567')

	def test_each_registration_is_new_identity(self):
		u1 = create_walk_in_user()
		u2 = create_walk_in_user()
		self.assertNotEqual(u1.pk, u2.pk)
		self.assertNotEqual(u1.email, u2.email)

	def test_walk_in_profile_complete_without_department(self):
		user = create_walk_in_user()
		PatientProfile.objects.filter(user=user).update(
			gender='female',
			civil_status='single',
			religion='Roman Catholic',
			citizenship='Filipino',
			date_of_birth=date(2000, 1, 15),
			place_of_birth='Manila',
			age=24,
			address='123 Main',
			zip_code='1000',
			phone='+639171234567',
			emergency_contact='Parent',
			emergency_phone='+639181112233',
			department='',
			course='',
			year_level='',
		)
		user = User.objects.select_related('patient_profile').get(pk=user.pk)
		missing = get_missing_profile_fields(user)
		self.assertEqual(missing, [], msg=f'missing={missing}')
		self.assertTrue(is_profile_complete(user))

	def test_walk_in_patient_id_readonly_and_ignores_post_tamper(self):
		user = create_walk_in_user()
		profile = user.patient_profile
		original_id = profile.patient_id
		self.assertTrue(original_id.startswith('WI-'))

		form = StudentProfileForm(instance=profile, user=user)
		self.assertTrue(form.fields['patient_id'].widget.attrs.get('readonly'))

		posted = {
			'patient_id': 'TAMPERED-999',
			'middle_name': '',
			'gender': 'female',
			'civil_status': 'single',
			'religion': 'Roman Catholic',
			'citizenship': 'Filipino',
			'date_of_birth': '2000-01-15',
			'place_of_birth': 'Manila',
			'age': '24',
			'address': '123 Main',
			'zip_code': '1000',
			'phone': '+639171234567',
			'telephone_number': '',
			'emergency_contact': 'Parent',
			'emergency_phone': '+639181112233',
			'department': '',
			'course': '',
			'year_level': '',
			'allergies': '',
			'medical_conditions': '',
		}
		bound = StudentProfileForm(data=posted, instance=profile, user=user)
		self.assertTrue(bound.is_valid(), msg=bound.errors.as_text())
		self.assertEqual(bound.cleaned_data['patient_id'], original_id)
		saved = bound.save()
		self.assertEqual(saved.patient_id, original_id)

	def test_walk_in_form_skips_academic_and_clears_employee_flag(self):
		user = create_walk_in_user()
		profile = user.patient_profile
		form = StudentProfileForm(instance=profile, user=user)
		for field_name in ('department', 'course', 'year_level', 'is_employee'):
			self.assertFalse(form.fields[field_name].required)

		posted = {
			'patient_id': profile.patient_id,
			'middle_name': '',
			'gender': 'female',
			'civil_status': 'single',
			'religion': 'Roman Catholic',
			'citizenship': 'Filipino',
			'date_of_birth': '2000-01-15',
			'place_of_birth': 'Manila',
			'age': '24',
			'address': '123 Main',
			'zip_code': '1000',
			'phone': '+639171234567',
			'telephone_number': '',
			'emergency_contact': 'Parent',
			'emergency_phone': '+639181112233',
			'is_employee': 'on',
			'department': 'College of Nursing',
			'course': 'BS Nursing',
			'year_level': '1st Year',
			'allergies': '',
			'medical_conditions': '',
		}
		bound = StudentProfileForm(data=posted, instance=profile, user=user)
		self.assertTrue(bound.is_valid(), msg=bound.errors.as_text())
		self.assertEqual(bound.cleaned_data['department'], '')
		self.assertEqual(bound.cleaned_data['course'], '')
		self.assertEqual(bound.cleaned_data['year_level'], '')
		self.assertFalse(bound.cleaned_data['is_employee'])
		saved = bound.save()
		self.assertFalse(saved.is_employee)
		self.assertEqual(saved.department, '')
		self.assertEqual(saved.course, '')
		self.assertEqual(saved.year_level, '')

	def test_walk_in_edit_profile_hides_academic_section(self):
		user = create_walk_in_user()
		client = Client()
		client.force_login(user)
		response = client.get(reverse('core:edit_profile'))
		self.assertEqual(response.status_code, 200)
		self.assertNotContains(response, 'Academic Information')
		self.assertNotContains(response, 'I am an employee')
		self.assertNotContains(response, 'studentAcademicEditForm')

	def test_guest_login_route_removed(self):
		client = Client()
		response = client.get('/auth/guest-login/')
		self.assertEqual(response.status_code, 404)


class RegisterWalkInPatientApiTests(TestCase):
	def setUp(self):
		self.staff = User.objects.create_user(
			email='staff-walkin@test.com',
			password='pass',
			role='staff',
		)
		_complete_staff_like_profile(self.staff, 'STAFF-WI-01')
		self.client = Client()
		self.client.force_login(self.staff)
		self.url = reverse('core:register_walk_in_patient')

	def test_denied_without_module_grant(self):
		response = self.client.post(
			self.url,
			data=json.dumps({
				'clinical_module': MODULE_MEDICAL_RECORDS,
				'first_name': 'Walk',
				'last_name': 'In',
			}),
			content_type='application/json',
		)
		self.assertEqual(response.status_code, 403)

	def test_creates_patient_with_module_grant(self):
		profile = self.staff.staff_profile
		profile.allowed_clinical_modules = [MODULE_MEDICAL_RECORDS]
		profile.save(update_fields=['allowed_clinical_modules'])

		response = self.client.post(
			self.url,
			data=json.dumps({
				'clinical_module': MODULE_MEDICAL_RECORDS,
				'first_name': 'Maria',
				'last_name': 'Santos',
			}),
			content_type='application/json',
		)
		self.assertEqual(response.status_code, 201)
		data = response.json()
		self.assertTrue(str(data['patient_id']).startswith('WI-'))
		self.assertEqual(data['name'], 'Maria Santos')
		created = User.objects.get(pk=data['id'])
		self.assertTrue(is_walk_in_user(created))

	def test_requires_names(self):
		profile = self.staff.staff_profile
		profile.allowed_clinical_modules = [MODULE_MEDICAL_RECORDS]
		profile.save(update_fields=['allowed_clinical_modules'])

		response = self.client.post(
			self.url,
			data=json.dumps({
				'clinical_module': MODULE_MEDICAL_RECORDS,
				'first_name': '',
				'last_name': 'Only',
			}),
			content_type='application/json',
		)
		self.assertEqual(response.status_code, 400)
