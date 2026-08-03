from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.doctor_access import MODULE_MANAGE_CONCERN
from core.models import CollegeDepartment, CourseProgram, PatientProfile, YearLevelOption
from core.tests import _complete_staff_like_profile

from .forms import ConcernRecordForm
from .models import ConcernRecord

User = get_user_model()


class ConcernRecordAccessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.college = CollegeDepartment.objects.create(name='College of Nursing')
        cls.program = CourseProgram.objects.create(
            college_department=cls.college,
            name='BS Nursing',
        )
        cls.year = YearLevelOption.objects.create(
            college_department=cls.college,
            name='3rd Year',
            sort_order=3,
        )
        cls.other_college = CollegeDepartment.objects.create(
            name='College of Business',
            course_optional=False,
        )
        cls.other_program = CourseProgram.objects.create(
            college_department=cls.other_college,
            name='BS Accountancy',
        )
        cls.optional_college = CollegeDepartment.objects.create(
            name='IBED - Junior High',
            course_optional=True,
        )
        cls.optional_year = YearLevelOption.objects.create(
            college_department=cls.optional_college,
            name='Grade 8',
            sort_order=8,
        )

        cls.admin = User.objects.create_user(
            email='admin-concern@test.com',
            password='pass',
            role='admin',
            first_name='Admin',
            last_name='User',
        )
        _complete_staff_like_profile(cls.admin, 'ADM-CONCERN-01')

        cls.staff = User.objects.create_user(
            email='staff-concern@test.com',
            password='pass',
            role='staff',
            first_name='Staff',
            last_name='User',
        )
        _complete_staff_like_profile(cls.staff, 'STAFF-CONCERN-01')
        profile = cls.staff.staff_profile
        profile.allowed_clinical_modules = [MODULE_MANAGE_CONCERN]
        profile.save(update_fields=['allowed_clinical_modules'])

        cls.staff_denied = User.objects.create_user(
            email='staff-denied-concern@test.com',
            password='pass',
            role='staff',
            first_name='Denied',
            last_name='Staff',
        )
        _complete_staff_like_profile(cls.staff_denied, 'STAFF-CONCERN-02')
        denied_profile = cls.staff_denied.staff_profile
        denied_profile.allowed_clinical_modules = []
        denied_profile.save(update_fields=['allowed_clinical_modules'])

        cls.student = User.objects.create_user(
            email='student-concern@test.com',
            password='pass',
            role='patient',
            first_name='Ana',
            last_name='Santos',
        )
        PatientProfile.objects.filter(user=cls.student).update(
            patient_id='STU-CONCERN-01',
            middle_name='Marie',
            department=cls.college.name,
            course=cls.program.name,
            year_level=cls.year.name,
            is_employee=False,
        )

        cls.employee = User.objects.create_user(
            email='employee-concern@test.com',
            password='pass',
            role='patient',
            first_name='Emp',
            last_name='Loyee',
        )
        PatientProfile.objects.filter(user=cls.employee).update(
            patient_id='EMP-CONCERN-01',
            department=cls.college.name,
            course='',
            year_level='',
            is_employee=True,
        )

    def _login(self, user):
        self.client.force_login(user)
        session = self.client.session
        session[f'profile_complete_{user.id}_{user.role}'] = True
        session.save()

    def test_admin_cannot_list(self):
        self._login(self.admin)
        response = self.client.get(reverse('manage_concern:concern_list'), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'You do not have permission')

    def test_staff_without_module_denied(self):
        self._login(self.staff_denied)
        response = self.client.get(reverse('manage_concern:concern_list'), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Not enabled for your account')

    def test_staff_with_module_can_create(self):
        self._login(self.staff)
        response = self.client.post(
            reverse('manage_concern:concern_create'),
            {
                'date': date.today().isoformat(),
                'time': '09:30',
                'first_name': 'Juan',
                'last_name': 'Dela Cruz',
                'middle_name': '',
                'affiliation_type': 'catalog',
                'college_department': self.college.pk,
                'department_other': '',
                'course_program': self.program.pk,
                'year_level': self.year.pk,
                'concerns': 'Headache',
                'management_treatment': 'Rest and observation',
                'disposition': 'Sent home',
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ConcernRecord.objects.count(), 1)
        record = ConcernRecord.objects.get()
        self.assertEqual(record.first_name, 'Juan')
        self.assertEqual(record.created_by_id, self.staff.id)
        self.assertEqual(record.college_department_id, self.college.id)
        self.assertEqual(record.course_program_id, self.program.id)
        self.assertEqual(record.year_level_id, self.year.id)
        self.assertEqual(
            response.url,
            reverse('manage_concern:concern_detail', args=[record.pk]),
        )

    def test_staff_can_view_detail(self):
        self._login(self.staff)
        record = ConcernRecord.objects.create(
            date=date.today(),
            time='09:30',
            first_name='Juan',
            last_name='Dela Cruz',
            affiliation_type='catalog',
            college_department=self.college,
            course_program=self.program,
            year_level=self.year,
            concerns='Headache',
            management_treatment='Rest and observation',
            disposition='Sent home',
            created_by=self.staff,
        )
        response = self.client.get(
            reverse('manage_concern:concern_detail', args=[record.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Juan Dela Cruz')
        self.assertContains(response, 'Headache')
        self.assertContains(response, 'Rest and observation')
        self.assertContains(response, 'Sent home')
        self.assertContains(response, 'Management / treatment')
        self.assertContains(response, reverse('manage_concern:concern_edit', args=[record.pk]))

    def test_list_search_and_filters(self):
        self._login(self.staff)
        ConcernRecord.objects.create(
            date=date.today(),
            time='09:30',
            first_name='Juan',
            last_name='Dela Cruz',
            affiliation_type='catalog',
            college_department=self.college,
            course_program=self.program,
            year_level=self.year,
            concerns='Headache',
            management_treatment='Rest',
            disposition='Home',
            created_by=self.staff,
        )
        ConcernRecord.objects.create(
            date=date.today(),
            time='10:00',
            first_name='Maria',
            last_name='Reyes',
            affiliation_type='employee',
            college_department=self.college,
            concerns='Back pain',
            management_treatment='Ice pack',
            disposition='Returned to work',
            created_by=self.staff,
        )

        list_url = reverse('manage_concern:concern_list')
        response = self.client.get(list_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="jmcfi-mc-list-filter-form"')
        self.assertContains(response, 'name="search"')
        self.assertContains(response, 'Juan Dela Cruz')
        self.assertContains(response, 'Maria Reyes')

        search_resp = self.client.get(list_url, {'search': 'Headache'})
        self.assertEqual(search_resp.status_code, 200)
        self.assertContains(search_resp, 'Juan Dela Cruz')
        self.assertNotContains(search_resp, 'Maria Reyes')

        emp_resp = self.client.get(list_url, {'affiliation': 'employee'})
        self.assertEqual(emp_resp.status_code, 200)
        self.assertContains(emp_resp, 'Maria Reyes')
        self.assertNotContains(emp_resp, 'Juan Dela Cruz')
        self.assertContains(emp_resp, '>Student</option>')
        self.assertNotContains(emp_resp, 'Student / catalog')
        self.assertContains(emp_resp, 'name="department"')
        self.assertNotContains(emp_resp, 'name="program"')
        self.assertNotContains(emp_resp, 'name="year_level"')

        others_resp = self.client.get(list_url, {'affiliation': 'others'})
        self.assertEqual(others_resp.status_code, 200)
        self.assertNotContains(others_resp, 'name="department"')
        self.assertNotContains(others_resp, 'name="program"')
        self.assertNotContains(others_resp, 'name="year_level"')

        dept_resp = self.client.get(list_url, {'department': self.college.pk})
        self.assertEqual(dept_resp.status_code, 200)
        self.assertContains(dept_resp, 'Juan Dela Cruz')
        self.assertContains(dept_resp, 'name="program"')
        self.assertContains(dept_resp, 'name="year_level"')
        self.assertContains(dept_resp, 'BS Nursing')
        self.assertContains(dept_resp, '3rd Year')
        self.assertNotContains(dept_resp, 'Select department first')

        no_dept_resp = self.client.get(list_url, {'affiliation': 'catalog'})
        self.assertEqual(no_dept_resp.status_code, 200)
        self.assertContains(no_dept_resp, 'Select department first')
        self.assertContains(no_dept_resp, 'disabled')

        program_resp = self.client.get(
            list_url,
            {'department': self.college.pk, 'program': self.program.pk},
        )
        self.assertEqual(program_resp.status_code, 200)
        self.assertContains(program_resp, 'Juan Dela Cruz')
        self.assertNotContains(program_resp, 'Maria Reyes')

        htmx_resp = self.client.get(
            list_url,
            {'search': 'Maria'},
            HTTP_HX_REQUEST='true',
        )
        self.assertEqual(htmx_resp.status_code, 200)
        self.assertContains(htmx_resp, 'jmcfi-mc-list-table-fragment')
        self.assertContains(htmx_resp, 'jmcfi-mc-list-filters')
        self.assertContains(htmx_resp, 'Maria Reyes')
        self.assertNotContains(htmx_resp, 'Juan Dela Cruz')

    def test_create_without_program_or_year(self):
        self._login(self.staff)
        response = self.client.post(
            reverse('manage_concern:concern_create'),
            {
                'date': date.today().isoformat(),
                'time': '10:00',
                'first_name': 'Walk',
                'last_name': 'In',
                'middle_name': '',
                'affiliation_type': 'catalog',
                'college_department': self.college.pk,
                'department_other': '',
                'course_program': '',
                'year_level': '',
                'concerns': 'Fever',
                'management_treatment': 'Paracetamol',
                'disposition': 'Home',
            },
        )
        self.assertEqual(response.status_code, 302)
        record = ConcernRecord.objects.get()
        self.assertIsNone(record.course_program_id)
        self.assertIsNone(record.year_level_id)

    def test_create_employee_affiliation(self):
        self._login(self.staff)
        response = self.client.post(
            reverse('manage_concern:concern_create'),
            {
                'date': date.today().isoformat(),
                'time': '11:15',
                'first_name': 'Emp',
                'last_name': 'Only',
                'middle_name': '',
                'affiliation_type': 'employee',
                'college_department': self.college.pk,
                'department_other': '',
                'course_program': '',
                'year_level': '',
                'concerns': 'Fatigue',
                'management_treatment': 'Rest',
                'disposition': 'Returned to work',
            },
        )
        self.assertEqual(response.status_code, 302)
        record = ConcernRecord.objects.get()
        self.assertEqual(record.affiliation_type, ConcernRecord.AffiliationType.EMPLOYEE)
        self.assertEqual(record.college_department_id, self.college.id)
        self.assertIsNone(record.course_program_id)
        self.assertIsNone(record.year_level_id)
        self.assertEqual(record.academic_label, self.college.name)

    def test_create_employee_requires_department(self):
        form = ConcernRecordForm(
            data={
                'date': date.today().isoformat(),
                'time': '11:15',
                'first_name': 'Emp',
                'last_name': 'Only',
                'affiliation_type': 'employee',
                'college_department': '',
                'department_other': '',
                'concerns': 'Fatigue',
                'management_treatment': 'Rest',
                'disposition': 'Returned to work',
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn('college_department', form.errors)

    def test_create_employee_with_others_department(self):
        form = ConcernRecordForm(
            data={
                'date': date.today().isoformat(),
                'time': '11:20',
                'first_name': 'Emp',
                'last_name': 'Custom',
                'affiliation_type': 'employee',
                'college_department': '',
                'department_other': 'Facilities Office',
                'course_program': '',
                'year_level': '',
                'concerns': 'Fatigue',
                'management_treatment': 'Rest',
                'disposition': 'Returned to work',
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        record = form.save()
        self.assertEqual(record.affiliation_type, ConcernRecord.AffiliationType.EMPLOYEE)
        self.assertIsNone(record.college_department_id)
        self.assertEqual(record.department_other, 'Facilities Office')
        self.assertEqual(record.academic_label, 'Facilities Office')

    def test_create_others_requires_manual_department(self):
        form = ConcernRecordForm(
            data={
                'date': date.today().isoformat(),
                'time': '09:00',
                'first_name': 'Other',
                'last_name': 'Guest',
                'affiliation_type': 'others',
                'college_department': '',
                'department_other': '',
                'concerns': 'x',
                'management_treatment': 'y',
                'disposition': 'z',
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn('department_other', form.errors)

        form_ok = ConcernRecordForm(
            data={
                'date': date.today().isoformat(),
                'time': '09:00',
                'first_name': 'Other',
                'last_name': 'Guest',
                'affiliation_type': 'others',
                'college_department': '',
                'department_other': 'City Hall',
                'concerns': 'x',
                'management_treatment': 'y',
                'disposition': 'z',
            }
        )
        self.assertTrue(form_ok.is_valid(), form_ok.errors)
        record = form_ok.save()
        self.assertEqual(record.affiliation_type, ConcernRecord.AffiliationType.OTHERS)
        self.assertEqual(record.department_other, 'City Hall')
        self.assertEqual(record.academic_label, 'City Hall')

    def test_create_for_employee_with_optional_program(self):
        """Catalog college still allows optional program/year for employee patients."""
        self._login(self.staff)
        response = self.client.post(
            reverse('manage_concern:concern_create'),
            {
                'date': date.today().isoformat(),
                'time': '11:00',
                'patient_user': self.employee.pk,
                'first_name': self.employee.first_name,
                'last_name': self.employee.last_name,
                'middle_name': '',
                'affiliation_type': 'catalog',
                'college_department': self.college.pk,
                'department_other': '',
                'course_program': self.program.pk,
                'year_level': self.year.pk,
                'concerns': 'Back pain',
                'management_treatment': 'Rest',
                'disposition': 'Returned to work',
            },
        )
        self.assertEqual(response.status_code, 302)
        record = ConcernRecord.objects.get()
        self.assertEqual(record.patient_user_id, self.employee.id)
        self.assertEqual(record.course_program_id, self.program.id)
        self.assertEqual(record.year_level_id, self.year.id)

    def test_reject_program_from_other_college(self):
        form = ConcernRecordForm(
            data={
                'date': date.today().isoformat(),
                'time': '09:00',
                'first_name': 'Mismatch',
                'last_name': 'Case',
                'affiliation_type': 'catalog',
                'college_department': self.college.pk,
                'department_other': '',
                'course_program': self.other_program.pk,
                'year_level': '',
                'concerns': 'x',
                'management_treatment': 'y',
                'disposition': 'z',
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn('course_program', form.errors)

    def test_course_optional_college_allows_empty_program(self):
        form = ConcernRecordForm(
            data={
                'date': date.today().isoformat(),
                'time': '09:00',
                'first_name': 'Ibed',
                'last_name': 'Student',
                'affiliation_type': 'catalog',
                'college_department': self.optional_college.pk,
                'department_other': '',
                'course_program': '',
                'year_level': self.optional_year.pk,
                'concerns': 'x',
                'management_treatment': 'y',
                'disposition': 'z',
            }
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_program_and_year_labels_are_bare_names(self):
        form = ConcernRecordForm()
        program_labels = [label for _, label in form.fields['course_program'].choices if _]
        year_labels = [label for _, label in form.fields['year_level'].choices if _]
        self.assertIn('BS Nursing', program_labels)
        self.assertNotIn(f'BS Nursing ({self.college.name})', program_labels)
        self.assertIn('3rd Year', year_labels)
        self.assertNotIn(f'3rd Year ({self.college.name})', year_labels)

    def test_create_form_includes_id_catalog_and_layout(self):
        self._login(self.staff)
        response = self.client.get(reverse('manage_concern:concern_create'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'mc-colleges')
        self.assertContains(response, 'mc-courses-by-college')
        self.assertContains(response, 'mc-year-levels-by-college')
        self.assertContains(response, 'mc-course-optional-by-college')
        self.assertContains(response, 'Department / College')
        self.assertContains(response, 'department-search')
        self.assertContains(response, 'selectDepartment')
        self.assertContains(response, 'populateSelectFromCatalog')
        self.assertContains(response, 'sm:grid-cols-2')
        self.assertContains(response, 'Employee')
        self.assertContains(response, 'Others')
        self.assertContains(response, 'Specify department')
        self.assertContains(response, 'id_department_other')
        self.assertContains(response, 'onEmployeeChange')
        self.assertContains(response, 'onOthersChange')
        self.assertNotContains(response, '__employee__')
        self.assertNotContains(response, '__others__')
        self.assertContains(response, 'id="id_college_department"')
        self.assertContains(response, 'type="hidden"', html=False)
        # Catalog entries use bare program names with ids
        self.assertContains(response, '"name": "BS Nursing"')
        self.assertContains(response, f'"id": {self.program.pk}')
        self.assertContains(response, f'"id": {self.college.pk}')
        self.assertContains(response, '"name": "College of Nursing"')

    def test_college_field_uses_hidden_fk_input(self):
        form = ConcernRecordForm()
        self.assertEqual(form.fields['college_department'].label, 'Department / College')
        self.assertEqual(
            form.fields['college_department'].widget.__class__.__name__,
            'HiddenInput',
        )
    def test_user_prefill_includes_academic_and_employee_flag(self):
        self._login(self.staff)
        student_resp = self.client.get(
            reverse('manage_concern:user_prefill', args=[self.student.pk])
        )
        self.assertEqual(student_resp.status_code, 200)
        student_data = student_resp.json()
        self.assertEqual(student_data['department'], self.college.name)
        self.assertEqual(student_data['course'], self.program.name)
        self.assertEqual(student_data['year_level'], self.year.name)
        self.assertFalse(student_data['is_employee'])
        self.assertEqual(student_data['middle_name'], 'Marie')

        emp_resp = self.client.get(
            reverse('manage_concern:user_prefill', args=[self.employee.pk])
        )
        self.assertEqual(emp_resp.status_code, 200)
        emp_data = emp_resp.json()
        self.assertEqual(emp_data['department'], self.college.name)
        self.assertEqual(emp_data['course'], '')
        self.assertEqual(emp_data['year_level'], '')
        self.assertTrue(emp_data['is_employee'])
