"""Tests for patient_category (student / employee / walk_in) and guest login."""

from datetime import date

from django.test import Client, TestCase
from django.urls import reverse

from core.forms import StudentProfileForm
from core.models import CollegeDepartment, CourseProgram, PatientProfile, User, YearLevelOption
from core.patient_category import (
	PATIENT_CATEGORY_EMPLOYEE,
	PATIENT_CATEGORY_STUDENT,
	PATIENT_CATEGORY_WALK_IN,
	SELECTABLE_PATIENT_CATEGORY_CHOICES,
	category_to_designation,
	normalize_patient_category,
	required_profile_fields_for_category,
)
from core.utils import get_missing_profile_fields, is_profile_complete
from core.walk_in_auth import create_walk_in_user


class PatientCategoryHelperTests(TestCase):
	def test_category_to_designation_passthrough(self):
		self.assertEqual(category_to_designation('student'), 'student')
		self.assertEqual(category_to_designation('employee'), 'employee')
		self.assertEqual(category_to_designation('walk_in'), 'walk_in')
		self.assertEqual(category_to_designation('guest'), 'walk_in')
		self.assertEqual(category_to_designation('patient'), 'student')

	def test_normalize_legacy_guest(self):
		self.assertEqual(normalize_patient_category('guest'), PATIENT_CATEGORY_WALK_IN)

	def test_required_fields_walk_in_drops_institutional(self):
		base = ['patient_id', 'department', 'course', 'year_level', 'phone']
		required = required_profile_fields_for_category(base, PATIENT_CATEGORY_WALK_IN)
		self.assertIn('patient_id', required)
		self.assertIn('phone', required)
		self.assertNotIn('department', required)
		self.assertNotIn('course', required)
		self.assertNotIn('year_level', required)

	def test_required_fields_employee_keeps_department_only(self):
		base = ['patient_id', 'department', 'course', 'year_level', 'phone']
		required = required_profile_fields_for_category(base, PATIENT_CATEGORY_EMPLOYEE)
		self.assertIn('department', required)
		self.assertNotIn('course', required)
		self.assertNotIn('year_level', required)

	def test_selectable_choices_exclude_walk_in(self):
		values = [v for v, _ in SELECTABLE_PATIENT_CATEGORY_CHOICES]
		self.assertEqual(values, [PATIENT_CATEGORY_STUDENT, PATIENT_CATEGORY_EMPLOYEE])


class PatientCategoryFormTests(TestCase):
	@classmethod
	def setUpTestData(cls):
		cls.college = CollegeDepartment.objects.create(name='College of Nursing', is_active=True)
		CourseProgram.objects.create(
			college_department=cls.college,
			name='BS Nursing',
			is_active=True,
		)
		YearLevelOption.objects.create(
			college_department=cls.college,
			name='1st Year',
			sort_order=1,
			is_active=True,
		)

	def _base_data(self, **overrides):
		data = {
			'patient_id': 'PAT-CAT-001',
			'patient_category': PATIENT_CATEGORY_STUDENT,
			'middle_name': '',
			'gender': 'female',
			'civil_status': 'single',
			'religion': 'Roman Catholic',
			'citizenship': 'Filipino',
			'date_of_birth': '2000-01-15',
			'place_of_birth': 'Manila',
			'age': '24',
			'address': '123 Main St',
			'zip_code': '1000',
			'phone': '+639171234567',
			'telephone_number': '',
			'emergency_contact': 'Parent Name',
			'emergency_phone': '+639181112233',
			'department': 'College of Nursing',
			'course': 'BS Nursing',
			'year_level': '1st Year',
			'blood_type': '',
			'allergies': '',
			'medical_conditions': '',
		}
		data.update(overrides)
		return data

	def test_student_cannot_self_select_walk_in(self):
		user = User.objects.create_user(
			email='student-cat@test.com',
			password='pw',
			role='patient',
			first_name='Stu',
			last_name='Dent',
		)
		profile, _ = PatientProfile.objects.get_or_create(
			user=user,
			defaults={'patient_id': 'STU-001'},
		)
		profile.patient_id = 'STU-001'
		profile.patient_category = PATIENT_CATEGORY_STUDENT
		profile.save(update_fields=['patient_id', 'patient_category'])
		form = StudentProfileForm(
			data=self._base_data(
				patient_id='STU-001',
				patient_category=PATIENT_CATEGORY_WALK_IN,
			),
			instance=profile,
			user=user,
		)
		self.assertFalse(form.is_valid())
		self.assertIn('patient_category', form.errors)

	def test_walk_in_clears_institutional_fields(self):
		user = User.objects.create_user(
			email='walkin-cat@test.com',
			password='pw',
			role='patient',
			first_name='Walk',
			last_name='In',
		)
		profile, _ = PatientProfile.objects.get_or_create(
			user=user,
			defaults={'patient_id': 'WI-TEST01'},
		)
		profile.patient_id = 'WI-TEST01'
		profile.patient_category = PATIENT_CATEGORY_WALK_IN
		profile.save(update_fields=['patient_id', 'patient_category'])
		form = StudentProfileForm(
			data=self._base_data(
				patient_id='WI-TEST01',
				patient_category=PATIENT_CATEGORY_WALK_IN,
				department='College of Nursing',
				course='BS Nursing',
				year_level='1st Year',
			),
			instance=profile,
			user=user,
		)
		self.assertTrue(form.is_valid(), form.errors)
		saved = form.save()
		self.assertEqual(saved.patient_category, PATIENT_CATEGORY_WALK_IN)
		self.assertEqual(saved.department, '')
		self.assertEqual(saved.course, '')
		self.assertEqual(saved.year_level, '')

	def test_employee_requires_department_and_clears_course(self):
		user = User.objects.create_user(
			email='emp-cat@test.com',
			password='pw',
			role='patient',
			first_name='Emp',
			last_name='User',
		)
		profile, _ = PatientProfile.objects.get_or_create(
			user=user,
			defaults={'patient_id': 'EMP-001'},
		)
		profile.patient_id = 'EMP-001'
		profile.save(update_fields=['patient_id'])
		form = StudentProfileForm(
			data=self._base_data(
				patient_id='EMP-001',
				patient_category=PATIENT_CATEGORY_EMPLOYEE,
				department='',
				course='BS Nursing',
				year_level='1st Year',
			),
			instance=profile,
			user=user,
		)
		self.assertFalse(form.is_valid())
		self.assertIn('department', form.errors)

		form = StudentProfileForm(
			data=self._base_data(
				patient_id='EMP-001',
				patient_category=PATIENT_CATEGORY_EMPLOYEE,
				department='College of Nursing',
				course='BS Nursing',
				year_level='1st Year',
			),
			instance=profile,
			user=user,
		)
		self.assertTrue(form.is_valid(), form.errors)
		saved = form.save()
		self.assertEqual(saved.patient_category, PATIENT_CATEGORY_EMPLOYEE)
		self.assertEqual(saved.department, 'College of Nursing')
		self.assertEqual(saved.course, '')
		self.assertEqual(saved.year_level, '')

	def test_walk_in_profile_complete_without_department(self):
		user = User.objects.create_user(
			email='walkin-complete@test.com',
			password='pw',
			role='patient',
			first_name='Walk',
			last_name='Done',
			is_active=True,
		)
		PatientProfile.objects.filter(user=user).update(
			patient_id='WI-DONE01',
			patient_category=PATIENT_CATEGORY_WALK_IN,
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
		self.assertEqual(missing, [], msg=f'missing={missing} category={user.patient_profile.patient_category}')
		self.assertTrue(is_profile_complete(user))


class GuestLoginTests(TestCase):
	def test_create_walk_in_user_sets_category(self):
		user = create_walk_in_user()
		self.assertEqual(user.role, 'patient')
		self.assertTrue(user.email.endswith('@walkin.local'))
		self.assertFalse(user.has_usable_password())
		profile = user.patient_profile
		self.assertEqual(profile.patient_category, PATIENT_CATEGORY_WALK_IN)
		self.assertTrue(profile.patient_id.startswith('WI-'))

	def test_guest_login_creates_session_and_redirects(self):
		client = Client()
		response = client.get(reverse('core:guest_login'))
		self.assertEqual(response.status_code, 302)
		self.assertEqual(response.url, reverse('core:profile_required'))
		# Session should be authenticated as the new walk-in user
		response2 = client.get(reverse('core:profile_required'))
		self.assertEqual(response2.status_code, 200)
		self.assertTrue(response2.wsgi_request.user.is_authenticated)
		self.assertEqual(
			response2.wsgi_request.user.patient_profile.patient_category,
			PATIENT_CATEGORY_WALK_IN,
		)

	def test_each_guest_login_is_new_identity(self):
		u1 = create_walk_in_user()
		u2 = create_walk_in_user()
		self.assertNotEqual(u1.pk, u2.pk)
		self.assertNotEqual(u1.email, u2.email)
