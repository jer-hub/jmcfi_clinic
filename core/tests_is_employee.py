"""Tests for PatientProfile.is_employee academic behavior."""

from datetime import date

from django.test import TestCase

from core.forms import StudentProfileForm
from core.models import CollegeDepartment, CourseProgram, PatientProfile, User, YearLevelOption
from core.utils import get_missing_profile_fields, is_profile_complete


class IsEmployeeFormTests(TestCase):
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
			'patient_id': 'EMP-TEST-001',
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

	def test_employee_clears_course_and_year(self):
		user = User.objects.create_user(
			email='emp-flag@test.com',
			password='pw',
			role='patient',
			first_name='Emp',
			last_name='User',
		)
		profile, _ = PatientProfile.objects.get_or_create(
			user=user,
			defaults={'patient_id': 'EMP-TEST-001'},
		)
		profile.patient_id = 'EMP-TEST-001'
		profile.save(update_fields=['patient_id'])
		form = StudentProfileForm(
			data=self._base_data(is_employee='on'),
			instance=profile,
			user=user,
		)
		self.assertTrue(form.is_valid(), form.errors)
		saved = form.save()
		self.assertTrue(saved.is_employee)
		self.assertEqual(saved.department, 'College of Nursing')
		self.assertEqual(saved.course, '')
		self.assertEqual(saved.year_level, '')

	def test_employee_requires_department(self):
		user = User.objects.create_user(
			email='emp-dept@test.com',
			password='pw',
			role='patient',
			first_name='Emp',
			last_name='Dept',
		)
		profile, _ = PatientProfile.objects.get_or_create(
			user=user,
			defaults={'patient_id': 'EMP-DEPT-001'},
		)
		profile.patient_id = 'EMP-DEPT-001'
		profile.save(update_fields=['patient_id'])
		form = StudentProfileForm(
			data=self._base_data(
				patient_id='EMP-DEPT-001',
				is_employee='on',
				department='',
				course='',
				year_level='',
			),
			instance=profile,
			user=user,
		)
		self.assertFalse(form.is_valid())
		self.assertIn('department', form.errors)

	def test_student_still_requires_course(self):
		user = User.objects.create_user(
			email='stu-flag@test.com',
			password='pw',
			role='patient',
			first_name='Stu',
			last_name='Dent',
		)
		profile, _ = PatientProfile.objects.get_or_create(
			user=user,
			defaults={'patient_id': 'STU-TEST-001'},
		)
		profile.patient_id = 'STU-TEST-001'
		profile.save(update_fields=['patient_id'])
		form = StudentProfileForm(
			data=self._base_data(
				patient_id='STU-TEST-001',
				course='',
				year_level='1st Year',
			),
			instance=profile,
			user=user,
		)
		self.assertFalse(form.is_valid())
		self.assertIn('course', form.errors)

	def test_employee_profile_complete_without_course(self):
		user = User.objects.create_user(
			email='emp-complete@test.com',
			password='pw',
			role='patient',
			first_name='Emp',
			last_name='Done',
			is_active=True,
		)
		PatientProfile.objects.filter(user=user).update(
			patient_id='EMP-DONE-001',
			is_employee=True,
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
			department='College of Nursing',
			course='',
			year_level='',
		)
		user = User.objects.select_related('patient_profile').get(pk=user.pk)
		missing = get_missing_profile_fields(user)
		self.assertEqual(missing, [], msg=f'missing={missing}')
		self.assertTrue(is_profile_complete(user))
