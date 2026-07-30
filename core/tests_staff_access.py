from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.doctor_access import (
    MODULE_APPOINTMENTS,
    MODULE_DOCUMENT_REQUEST,
    MODULE_HEALTH_PROFILE_FORMS,
    MODULE_PHARMACY,
    MODULE_PRESCRIPTIONS,
    has_clinical_module,
    normalize_module_list,
)
from core.forms import StaffProfileForm
from core.nav_context import nav_bar_context
from core.tests import _complete_doctor_profile, _complete_staff_like_profile

User = get_user_model()


class StaffAccessHelpersTests(TestCase):
    def test_empty_grant_denies_modules_for_staff(self):
        staff = User.objects.create_user(
            email='staff-empty@test.com',
            password='pass',
            role='staff',
        )
        _complete_staff_like_profile(staff, 'STAFF-EMPTY-01')
        self.assertFalse(has_clinical_module(staff, MODULE_APPOINTMENTS))
        self.assertFalse(has_clinical_module(staff, MODULE_PHARMACY))

    def test_normalize_strips_document_request_for_staff_allowed_set(self):
        from core.doctor_access import STAFF_CLINICAL_MODULE_CHOICES

        allowed = frozenset(k for k, _ in STAFF_CLINICAL_MODULE_CHOICES)
        cleaned = normalize_module_list(
            [MODULE_PHARMACY, MODULE_DOCUMENT_REQUEST, MODULE_APPOINTMENTS],
            allowed_keys=allowed,
        )
        self.assertEqual(set(cleaned), {MODULE_PHARMACY, MODULE_APPOINTMENTS})
        self.assertNotIn(MODULE_DOCUMENT_REQUEST, cleaned)


class StaffAccessUrlTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            email='staff-url@test.com',
            password='pass',
            role='staff',
            first_name='St',
            last_name='Aff',
        )
        _complete_staff_like_profile(self.staff, 'STAFF-URL-01')
        self.client.force_login(self.staff)
        session = self.client.session
        session[f'profile_complete_{self.staff.id}_{self.staff.role}'] = True
        session.save()

    def test_empty_grant_blocks_appointments_pharmacy_and_health_forms(self):
        appt = self.client.get(reverse('appointments:appointment_list'), follow=True)
        self.assertContains(appt, 'Not enabled for your account')

        pharm = self.client.get(reverse('pharmacy:dashboard'), follow=True)
        self.assertContains(pharm, 'Not enabled for your account')

        forms = self.client.get(reverse('health_forms_services:forms_list'), follow=True)
        self.assertContains(forms, 'Not enabled for your account')

    def test_partial_grant_allows_pharmacy_and_one_health_form(self):
        profile = self.staff.staff_profile
        profile.allowed_clinical_modules = [MODULE_PHARMACY, MODULE_HEALTH_PROFILE_FORMS]
        profile.save(update_fields=['allowed_clinical_modules'])

        ok_pharm = self.client.get(reverse('pharmacy:dashboard'))
        self.assertEqual(ok_pharm.status_code, 200)
        self.assertNotContains(ok_pharm, 'Not enabled for your account')

        ok_forms = self.client.get(reverse('health_forms_services:forms_list'))
        self.assertEqual(ok_forms.status_code, 200)
        self.assertNotContains(ok_forms, 'Not enabled for your account')

        denied = self.client.get(reverse('appointments:appointment_list'), follow=True)
        self.assertContains(denied, 'Not enabled for your account')

        denied_rx = self.client.get(
            reverse('health_forms_services:prescription_list'),
            follow=True,
        )
        self.assertContains(denied_rx, 'Not enabled for your account')

    def test_nav_context_empty_when_no_grants(self):
        request = self.client.get(reverse('core:dashboard')).wsgi_request
        request.user = self.staff
        ctx = nav_bar_context(request)
        self.assertFalse(ctx['clinical_nav']['show_services'])
        self.assertFalse(ctx['clinical_nav']['show_health_forms'])
        self.assertFalse(ctx['doctor_nav']['show_services'])


class StaffAccessAdminPersistTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email='admin-staff-mod@test.com',
            password='pass',
            role='admin',
            first_name='Ad',
            last_name='Min',
        )
        _complete_staff_like_profile(self.admin, 'ADM-STF-01')
        self.staff = User.objects.create_user(
            email='staff-persist@test.com',
            password='pass',
            role='staff',
            first_name='St',
            last_name='Persist',
            is_active=True,
        )
        _complete_staff_like_profile(self.staff, 'STAFF-PERSIST-01')
        self.client.force_login(self.admin)
        session = self.client.session
        session[f'profile_complete_{self.admin.id}_{self.admin.role}'] = True
        session.save()

    def test_admin_edit_persists_staff_modules(self):
        profile = self.staff.staff_profile
        response = self.client.post(
            reverse('core:user_edit', kwargs={'user_id': self.staff.id}),
            {
                'email': self.staff.email,
                'first_name': self.staff.first_name,
                'last_name': self.staff.last_name,
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
                'position': profile.position or 'Nurse',
                'specialization': profile.specialization or '',
                'license_number': profile.license_number or '',
                'ptr_no': profile.ptr_no or '',
                'blood_type': profile.blood_type or '',
                'allergies': profile.allergies or '',
                'medical_conditions': profile.medical_conditions or '',
                'allowed_clinical_modules': [MODULE_PHARMACY, MODULE_PRESCRIPTIONS],
            },
        )
        self.assertEqual(response.status_code, 302)
        profile.refresh_from_db()
        self.assertEqual(
            set(profile.allowed_clinical_modules),
            {MODULE_PHARMACY, MODULE_PRESCRIPTIONS},
        )

    def test_edit_form_shows_pharmacy_not_document_request(self):
        response = self.client.get(
            reverse('core:user_edit', kwargs={'user_id': self.staff.id}),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Services & Health Forms access')
        self.assertContains(response, 'value="pharmacy"')
        self.assertNotContains(response, 'value="document_request"')

    def test_staff_form_exposes_modules_only_for_admin_editing_staff(self):
        form = StaffProfileForm(
            instance=self.staff.staff_profile,
            user=self.staff,
            editor=self.admin,
        )
        self.assertIn('allowed_clinical_modules', form.fields)
        values = {c[0] for c in form.fields['allowed_clinical_modules'].choices}
        self.assertIn(MODULE_PHARMACY, values)
        self.assertNotIn(MODULE_DOCUMENT_REQUEST, values)


class DoctorCannotGrantPharmacyViaNormalize(TestCase):
    def test_doctor_choices_exclude_pharmacy(self):
        from core.doctor_access import DOCTOR_CLINICAL_MODULE_CHOICES

        keys = {k for k, _ in DOCTOR_CLINICAL_MODULE_CHOICES}
        self.assertNotIn(MODULE_PHARMACY, keys)
        self.assertIn(MODULE_DOCUMENT_REQUEST, keys)

    def test_doctor_admin_form_excludes_pharmacy(self):
        admin = User.objects.create_user(
            email='admin-doc-ph@test.com',
            password='pass',
            role='admin',
        )
        _complete_staff_like_profile(admin, 'ADM-DOC-PH')
        doctor = User.objects.create_user(
            email='doc-no-pharm@test.com',
            password='pass',
            role='doctor',
        )
        _complete_doctor_profile(doctor, 'DOC-NO-PH')
        form = StaffProfileForm(
            instance=doctor.staff_profile,
            user=doctor,
            editor=admin,
        )
        values = {c[0] for c in form.fields['allowed_clinical_modules'].choices}
        self.assertNotIn(MODULE_PHARMACY, values)
        self.assertIn(MODULE_DOCUMENT_REQUEST, values)
