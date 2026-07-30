from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.doctor_access import (
    MODULE_APPOINTMENTS,
    MODULE_HEALTH_PROFILE_FORMS,
    MODULE_PRESCRIPTIONS,
    doctor_has_module,
    granted_modules,
)
from core.forms import StaffProfileForm
from core.nav_context import nav_bar_context
from core.tests import _complete_doctor_profile, _complete_staff_like_profile

User = get_user_model()


class DoctorAccessHelpersTests(TestCase):
    def test_empty_grant_denies_modules_for_doctor(self):
        doctor = User.objects.create_user(
            email='doc-empty@test.com',
            password='pass',
            role='doctor',
        )
        _complete_doctor_profile(doctor, 'DOC-EMPTY-01')
        self.assertEqual(granted_modules(doctor), set())
        self.assertFalse(doctor_has_module(doctor, MODULE_APPOINTMENTS))

    def test_staff_without_grants_is_denied(self):
        staff = User.objects.create_user(
            email='staff-access@test.com',
            password='pass',
            role='staff',
        )
        _complete_staff_like_profile(staff, 'STAFF-ACC-01')
        self.assertFalse(doctor_has_module(staff, MODULE_APPOINTMENTS))
        self.assertFalse(doctor_has_module(staff, MODULE_PRESCRIPTIONS))

    def test_patient_still_bypasses_opt_in_gate(self):
        patient = User.objects.create_user(
            email='patient-access@test.com',
            password='pass',
            role='patient',
        )
        self.assertTrue(doctor_has_module(patient, MODULE_APPOINTMENTS))


class DoctorAccessUrlTests(TestCase):
    def setUp(self):
        self.doctor = User.objects.create_user(
            email='doc-url@test.com',
            password='pass',
            role='doctor',
            first_name='Doc',
            last_name='Url',
        )
        _complete_doctor_profile(self.doctor, 'DOC-URL-01')
        self.client.force_login(self.doctor)
        session = self.client.session
        session[f'profile_complete_{self.doctor.id}_{self.doctor.role}'] = True
        session.save()

    def test_empty_grant_blocks_appointments_and_health_forms(self):
        appt = self.client.get(reverse('appointments:appointment_list'), follow=True)
        self.assertEqual(appt.status_code, 200)
        self.assertContains(appt, 'Not enabled for your account')

        forms = self.client.get(reverse('health_forms_services:forms_list'), follow=True)
        self.assertEqual(forms.status_code, 200)
        self.assertContains(forms, 'Not enabled for your account')

    def test_partial_grant_allows_only_granted_modules(self):
        profile = self.doctor.staff_profile
        profile.allowed_clinical_modules = [MODULE_APPOINTMENTS, MODULE_HEALTH_PROFILE_FORMS]
        profile.save(update_fields=['allowed_clinical_modules'])

        ok_appt = self.client.get(reverse('appointments:appointment_list'))
        self.assertEqual(ok_appt.status_code, 200)
        self.assertNotContains(ok_appt, 'Not enabled for your account')

        ok_forms = self.client.get(reverse('health_forms_services:forms_list'))
        self.assertEqual(ok_forms.status_code, 200)
        self.assertNotContains(ok_forms, 'Not enabled for your account')

        denied = self.client.get(
            reverse('health_forms_services:prescription_list'),
            follow=True,
        )
        self.assertContains(denied, 'Not enabled for your account')

        denied_med = self.client.get(reverse('medical_records:medical_records'), follow=True)
        self.assertContains(denied_med, 'Not enabled for your account')

    def test_nav_context_empty_when_no_grants(self):
        request = self.client.get(reverse('core:dashboard')).wsgi_request
        request.user = self.doctor
        ctx = nav_bar_context(request)
        self.assertFalse(ctx['doctor_nav']['show_services'])
        self.assertFalse(ctx['doctor_nav']['show_health_forms'])

    def test_staff_still_reaches_health_forms_when_granted(self):
        staff = User.objects.create_user(
            email='staff-hf@test.com',
            password='pass',
            role='staff',
            first_name='St',
            last_name='Aff',
        )
        _complete_staff_like_profile(staff, 'STAFF-HF-01')
        staff.staff_profile.allowed_clinical_modules = [MODULE_HEALTH_PROFILE_FORMS]
        staff.staff_profile.save(update_fields=['allowed_clinical_modules'])
        self.client.force_login(staff)
        session = self.client.session
        session[f'profile_complete_{staff.id}_{staff.role}'] = True
        session.save()
        response = self.client.get(reverse('health_forms_services:forms_list'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Not enabled for your account')


class DoctorAccessAdminPersistTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email='admin-mod@test.com',
            password='pass',
            role='admin',
            first_name='Ad',
            last_name='Min',
        )
        _complete_staff_like_profile(self.admin, 'ADM-MOD-01')
        self.doctor = User.objects.create_user(
            email='doc-persist@test.com',
            password='pass',
            role='doctor',
            first_name='Doc',
            last_name='Persist',
            is_active=True,
        )
        _complete_doctor_profile(self.doctor, 'DOC-PERSIST-01')
        self.client.force_login(self.admin)
        session = self.client.session
        session[f'profile_complete_{self.admin.id}_{self.admin.role}'] = True
        session.save()

    def test_admin_edit_persists_modules(self):
        profile = self.doctor.staff_profile
        response = self.client.post(
            reverse('core:user_edit', kwargs={'user_id': self.doctor.id}),
            {
                'email': self.doctor.email,
                'first_name': self.doctor.first_name,
                'last_name': self.doctor.last_name,
                'is_active': 'on',
                'staff_id': profile.staff_id,
                'middle_name': profile.middle_name,
                'gender': profile.gender,
                'civil_status': profile.civil_status,
                'religion': profile.religion,
                'citizenship': profile.citizenship,
                'date_of_birth': profile.date_of_birth.isoformat()
                if hasattr(profile.date_of_birth, 'isoformat')
                else profile.date_of_birth,
                'place_of_birth': profile.place_of_birth,
                'age': profile.age or 26,
                'address': profile.address,
                'zip_code': profile.zip_code,
                'phone': profile.phone,
                'telephone_number': profile.telephone_number or '',
                'emergency_contact': profile.emergency_contact,
                'emergency_phone': profile.emergency_phone,
                'department': profile.department,
                'position': profile.position or 'Physician',
                'specialization': profile.specialization or '',
                'license_number': profile.license_number or 'LIC-1',
                'ptr_no': profile.ptr_no or '',
                'allowed_clinical_modules': [
                    MODULE_APPOINTMENTS,
                    MODULE_PRESCRIPTIONS,
                ],
            },
        )
        self.assertEqual(response.status_code, 302)
        profile.refresh_from_db()
        self.assertEqual(
            set(profile.allowed_clinical_modules),
            {MODULE_APPOINTMENTS, MODULE_PRESCRIPTIONS},
        )

    def test_edit_form_shows_access_section(self):
        response = self.client.get(
            reverse('core:user_edit', kwargs={'user_id': self.doctor.id}),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Services & Health Forms access')
        self.assertContains(response, 'name="allowed_clinical_modules"')

    def test_staff_profile_form_exposes_modules_only_for_admin_editing_doctor(self):
        form = StaffProfileForm(
            instance=self.doctor.staff_profile,
            user=self.doctor,
            editor=self.admin,
        )
        self.assertIn('allowed_clinical_modules', form.fields)

        self_form = StaffProfileForm(
            instance=self.doctor.staff_profile,
            user=self.doctor,
            editor=self.doctor,
        )
        self.assertNotIn('allowed_clinical_modules', self_form.fields)
