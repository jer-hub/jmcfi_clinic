import json
from datetime import datetime, time, timedelta

from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from appointments.models import Appointment, AppointmentTypeDefault
from appointments.views import _get_schedule_context
from core.doctor_access import MODULE_APPOINTMENTS
from core.guest_auth import GUEST_EMAIL_DOMAIN, is_guest_user
from core.models import PatientProfile, StaffProfile, User
from core.tests import _complete_staff_like_profile


@override_settings(
    MIDDLEWARE=[
        middleware
        for middleware in settings.MIDDLEWARE
        if middleware != 'core.middleware.ProfileCompleteMiddleware'
    ]
)
class ScheduleAppointmentDoctorFilterTests(TestCase):
    def setUp(self):
        self.patient = User.objects.create_user(
            email='patient-sched@test.com',
            password='pass1234',
            role='patient',
            first_name='Pat',
            last_name='Ient',
        )
        profile, _ = PatientProfile.objects.get_or_create(user=self.patient)
        profile.patient_id = 'S-SCHED-001'
        profile.date_of_birth = '2004-01-01'
        profile.phone = '09123456789'
        profile.emergency_contact = 'Parent'
        profile.emergency_phone = '09999999999'
        profile.blood_type = 'O+'
        profile.save()

        self.assigned_doctor = User.objects.create_user(
            email='assigned-doc@test.com',
            password='pass1234',
            role='doctor',
            first_name='Assigned',
            last_name='Doctor',
        )
        StaffProfile.objects.update_or_create(
            user=self.assigned_doctor,
            defaults={
                'staff_id': 'D-ASSIGNED',
                'department': 'Dental',
                'phone': '09111111111',
                'license_number': 'LIC-A',
                'ptr_no': 'PTR-A',
            },
        )

        self.other_doctor = User.objects.create_user(
            email='other-doc@test.com',
            password='pass1234',
            role='doctor',
            first_name='Other',
            last_name='Doctor',
        )
        StaffProfile.objects.update_or_create(
            user=self.other_doctor,
            defaults={
                'staff_id': 'D-OTHER',
                'department': 'General',
                'phone': '09222222222',
                'license_number': 'LIC-O',
                'ptr_no': 'PTR-O',
            },
        )

        self.dental_default, _ = AppointmentTypeDefault.objects.update_or_create(
            appointment_type='dental',
            defaults={'is_active': True},
        )
        self.dental_default.assigned_doctors.set([self.assigned_doctor])

        self.consult_default, _ = AppointmentTypeDefault.objects.update_or_create(
            appointment_type='consultation',
            defaults={'is_active': True},
        )
        self.consult_default.assigned_doctors.set([self.other_doctor])

    def test_schedule_context_only_includes_assigned_doctors(self):
        ctx = _get_schedule_context()
        doctor_ids = {doctor.id for doctor in ctx['doctors']}
        self.assertEqual(doctor_ids, {self.assigned_doctor.id, self.other_doctor.id})

        type_map = json.loads(ctx['type_doctor_map'])
        self.assertEqual(type_map['dental'], [self.assigned_doctor.id])
        self.assertEqual(type_map['consultation'], [self.other_doctor.id])

    def test_schedule_page_exposes_type_doctor_map_for_filtering(self):
        self.client.force_login(self.patient)
        response = self.client.get(reverse('appointments:schedule_appointment'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'"dental": [{self.assigned_doctor.id}]')
        self.assertContains(response, f'"id": "{self.assigned_doctor.id}"')
        self.assertContains(response, 'if (!Array.isArray(allowed) || allowed.length === 0) return []')

    def test_post_rejects_doctor_not_assigned_to_type(self):
        self.client.force_login(self.patient)
        appointment_date = (timezone.now().date() + timedelta(days=7)).isoformat()
        while datetime.strptime(appointment_date, '%Y-%m-%d').date().weekday() >= 5:
            appointment_date = (
                datetime.strptime(appointment_date, '%Y-%m-%d').date() + timedelta(days=1)
            ).isoformat()

        response = self.client.post(
            reverse('appointments:schedule_appointment'),
            {
                'appointment_type': 'dental',
                'doctor': self.other_doctor.id,
                'date': appointment_date,
                'time': '09:00',
                'reason': 'Tooth pain',
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'not available for this appointment type')

    def test_post_rejects_type_with_no_assigned_doctors(self):
        self.dental_default.assigned_doctors.clear()
        self.client.force_login(self.patient)
        appointment_date = (timezone.now().date() + timedelta(days=7)).isoformat()
        while datetime.strptime(appointment_date, '%Y-%m-%d').date().weekday() >= 5:
            appointment_date = (
                datetime.strptime(appointment_date, '%Y-%m-%d').date() + timedelta(days=1)
            ).isoformat()

        response = self.client.post(
            reverse('appointments:schedule_appointment'),
            {
                'appointment_type': 'dental',
                'doctor': self.assigned_doctor.id,
                'date': appointment_date,
                'time': '09:00',
                'reason': 'Tooth pain',
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'No doctors are available for this appointment type')


@override_settings(
    MIDDLEWARE=[
        middleware
        for middleware in settings.MIDDLEWARE
        if middleware != 'core.middleware.ProfileCompleteMiddleware'
    ],
    STORAGES={
        'default': {
            'BACKEND': 'django.core.files.storage.FileSystemStorage',
        },
        'staticfiles': {
            'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
        },
    },
)
class ScheduleForPatientAssignedTypesTests(TestCase):
    def setUp(self):
        self.patient = User.objects.create_user(
            email='patient-sfp@test.com',
            password='pass1234',
            role='patient',
            first_name='Pat',
            last_name='Ient',
        )
        profile, _ = PatientProfile.objects.get_or_create(user=self.patient)
        profile.patient_id = 'S-SFP-001'
        profile.date_of_birth = '2004-01-01'
        profile.phone = '09123456789'
        profile.emergency_contact = 'Parent'
        profile.emergency_phone = '09999999999'
        profile.blood_type = 'O+'
        profile.save()

        self.assigned_doctor = User.objects.create_user(
            email='sfp-assigned-doc@test.com',
            password='pass1234',
            role='doctor',
            first_name='Assigned',
            last_name='Doctor',
        )
        _complete_staff_like_profile(self.assigned_doctor, 'D-SFP-ASSIGNED')
        StaffProfile.objects.filter(user=self.assigned_doctor).update(
            license_number='LIC-SFP-A',
            ptr_no='PTR-SFP-A',
            allowed_clinical_modules=[MODULE_APPOINTMENTS],
        )

        self.other_doctor = User.objects.create_user(
            email='sfp-other-doc@test.com',
            password='pass1234',
            role='doctor',
            first_name='Other',
            last_name='Doctor',
        )
        _complete_staff_like_profile(self.other_doctor, 'D-SFP-OTHER')
        StaffProfile.objects.filter(user=self.other_doctor).update(
            license_number='LIC-SFP-O',
            ptr_no='PTR-SFP-O',
            allowed_clinical_modules=[MODULE_APPOINTMENTS],
        )

        self.staff = User.objects.create_user(
            email='sfp-staff@test.com',
            password='pass1234',
            role='staff',
            first_name='Clinic',
            last_name='Staff',
        )
        _complete_staff_like_profile(self.staff, 'STF-SFP')
        StaffProfile.objects.filter(user=self.staff).update(
            allowed_clinical_modules=[MODULE_APPOINTMENTS],
        )

        self.dental_default, _ = AppointmentTypeDefault.objects.update_or_create(
            appointment_type='dental',
            defaults={'is_active': True},
        )
        self.dental_default.assigned_doctors.set([self.assigned_doctor])

        self.consult_default, _ = AppointmentTypeDefault.objects.update_or_create(
            appointment_type='consultation',
            defaults={'is_active': True},
        )
        self.consult_default.assigned_doctors.set([self.other_doctor])

        appt_date = timezone.now().date() + timedelta(days=7)
        while appt_date.weekday() >= 5:
            appt_date += timedelta(days=1)
        self.appt_date = appt_date

    def test_doctor_schedule_page_only_shows_assigned_types(self):
        self.client.force_login(self.assigned_doctor)
        response = self.client.get(reverse('appointments:schedule_for_patient'))
        self.assertEqual(response.status_code, 200)
        type_keys = [key for key, _label in response.context['appointment_types']]
        self.assertEqual(type_keys, ['dental'])
        self.assertContains(response, 'value="dental"')
        self.assertNotContains(response, 'value="consultation"')

    def test_staff_schedule_page_shows_all_active_types(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse('appointments:schedule_for_patient'))
        self.assertEqual(response.status_code, 200)
        type_keys = {key for key, _label in response.context['appointment_types']}
        self.assertIn('consultation', type_keys)
        self.assertIn('dental', type_keys)

    def test_doctor_schedule_rejects_unassigned_type(self):
        self.client.force_login(self.assigned_doctor)
        response = self.client.post(
            reverse('appointments:schedule_for_patient'),
            {
                'patient': self.patient.id,
                'appointment_type': 'consultation',
                'date': self.appt_date.isoformat(),
                'time': '15:00',
                'reason': 'Unassigned type',
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'not available for this appointment type')
        self.assertFalse(
            Appointment.objects.filter(
                patient=self.patient,
                date=self.appt_date,
                time=time(15, 0),
            ).exists()
        )


def _next_weekday(days_ahead=7):
    day = timezone.localdate() + timedelta(days=days_ahead)
    while day.weekday() >= 5:
        day += timedelta(days=1)
    return day


@override_settings(
    MIDDLEWARE=[
        middleware
        for middleware in settings.MIDDLEWARE
        if middleware != 'core.middleware.ProfileCompleteMiddleware'
    ],
    STORAGES={
        'default': {
            'BACKEND': 'django.core.files.storage.FileSystemStorage',
        },
        'staticfiles': {
            'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
        },
    },
)
class SlotAvailabilityApiTests(TestCase):
    def setUp(self):
        self.patient = User.objects.create_user(
            email='slot-patient@test.com',
            password='pass1234',
            role='patient',
            first_name='Slot',
            last_name='Patient',
        )
        profile, _ = PatientProfile.objects.get_or_create(user=self.patient)
        profile.patient_id = 'S-SLOT-001'
        profile.date_of_birth = '2004-01-01'
        profile.phone = '09123456789'
        profile.emergency_contact = 'Parent'
        profile.emergency_phone = '09999999999'
        profile.blood_type = 'O+'
        profile.save()

        self.other_patient = User.objects.create_user(
            email='slot-other-patient@test.com',
            password='pass1234',
            role='patient',
            first_name='Other',
            last_name='Patient',
        )
        other_profile, _ = PatientProfile.objects.get_or_create(user=self.other_patient)
        other_profile.patient_id = 'S-SLOT-002'
        other_profile.date_of_birth = '2004-02-02'
        other_profile.phone = '09123456780'
        other_profile.emergency_contact = 'Parent'
        other_profile.emergency_phone = '09999999990'
        other_profile.blood_type = 'A+'
        other_profile.save()

        self.doctor = User.objects.create_user(
            email='slot-doctor@test.com',
            password='pass1234',
            role='doctor',
            first_name='Slot',
            last_name='Doctor',
        )
        _complete_staff_like_profile(self.doctor, 'D-SLOT')
        StaffProfile.objects.filter(user=self.doctor).update(
            allowed_clinical_modules=[MODULE_APPOINTMENTS],
        )

        self.staff = User.objects.create_user(
            email='slot-staff@test.com',
            password='pass1234',
            role='staff',
            first_name='Slot',
            last_name='Staff',
        )
        _complete_staff_like_profile(self.staff, 'STF-SLOT')
        StaffProfile.objects.filter(user=self.staff).update(
            allowed_clinical_modules=[MODULE_APPOINTMENTS],
        )

        self.other_doctor = User.objects.create_user(
            email='slot-other-doctor@test.com',
            password='pass1234',
            role='doctor',
            first_name='Other',
            last_name='Doctor',
        )
        _complete_staff_like_profile(self.other_doctor, 'D-SLOT-O')
        StaffProfile.objects.filter(user=self.other_doctor).update(
            allowed_clinical_modules=[MODULE_APPOINTMENTS],
        )

        self.appt_date = _next_weekday()
        Appointment.objects.create(
            patient=self.other_patient,
            doctor=self.doctor,
            appointment_type='consultation',
            date=self.appt_date,
            time=time(9, 0),
            reason='Existing booking',
            status='confirmed',
        )

    def _availability(self, **params):
        return self.client.get(reverse('appointments:slot_availability'), params)

    def test_patient_sees_occupied_slot(self):
        self.client.force_login(self.patient)
        response = self._availability(doctor=self.doctor.id, date=self.appt_date.isoformat())
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload['ok'])
        self.assertIn('09:00', payload['occupied'])
        self.assertEqual(payload['reasons'].get('09:00'), 'booked')
        self.assertIn('10:00', payload['available'])

    def test_missing_date_returns_400(self):
        self.client.force_login(self.patient)
        response = self._availability(doctor=self.doctor.id)
        self.assertEqual(response.status_code, 400)

    def test_staff_without_doctor_returns_400(self):
        self.client.force_login(self.staff)
        response = self._availability(date=self.appt_date.isoformat())
        self.assertEqual(response.status_code, 400)

    def test_doctor_defaults_to_self(self):
        self.client.force_login(self.doctor)
        response = self._availability(date=self.appt_date.isoformat())
        self.assertEqual(response.status_code, 200)
        self.assertIn('09:00', response.json()['occupied'])

    def test_patient_own_booking_marks_slot_occupied(self):
        Appointment.objects.create(
            patient=self.patient,
            doctor=self.other_doctor,
            appointment_type='consultation',
            date=self.appt_date,
            time=time(14, 0),
            reason='Own booking elsewhere',
            status='pending',
        )
        self.client.force_login(self.patient)
        payload = self._availability(
            doctor=self.doctor.id,
            date=self.appt_date.isoformat(),
        ).json()
        self.assertIn('14:00', payload['occupied'])
        self.assertEqual(payload['reasons'].get('14:00'), 'patient')

    def test_weekend_is_rejected(self):
        weekend = timezone.localdate()
        while weekend.weekday() < 5:
            weekend += timedelta(days=1)
        self.client.force_login(self.patient)
        response = self._availability(doctor=self.doctor.id, date=weekend.isoformat())
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertFalse(payload['ok'])
        self.assertIn('weekend', payload['error'].lower())

    def test_schedule_forms_disable_submit_until_slot_is_valid(self):
        self.client.force_login(self.patient)
        patient_page = self.client.get(reverse('appointments:schedule_appointment'))
        self.assertEqual(patient_page.status_code, 200)
        self.assertContains(patient_page, 'jmcfiAppointmentSlots')
        self.assertContains(patient_page, ':disabled="submitting || !dateTimeValid"')
        self.assertContains(patient_page, "isSlotOccupied('09:00')")
        self.assertContains(patient_page, 'Checking this date')
        self.assertContains(patient_page, 'fa-spinner fa-spin')

        self.client.force_login(self.staff)
        staff_page = self.client.get(reverse('appointments:schedule_for_patient'))
        self.assertEqual(staff_page.status_code, 200)
        self.assertContains(staff_page, 'jmcfiAppointmentSlots')
        self.assertContains(staff_page, ':disabled="submitting || !dateTimeValid || (!patientLocked && !hasScheduleTarget)"')
        self.assertContains(staff_page, "mode: 'collect'")
        self.assertContains(staff_page, 'created only when you schedule')


@override_settings(
    MIDDLEWARE=[
        middleware
        for middleware in settings.MIDDLEWARE
        if middleware != 'core.middleware.ProfileCompleteMiddleware'
    ],
    STORAGES={
        'default': {
            'BACKEND': 'django.core.files.storage.FileSystemStorage',
        },
        'staticfiles': {
            'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
        },
    },
)
class ScheduleGuestDeferredCreateTests(TestCase):
    def setUp(self):
        self.doctor = User.objects.create_user(
            email='guest-defer-doc@test.com',
            password='pass1234',
            role='doctor',
            first_name='Defer',
            last_name='Doctor',
        )
        _complete_staff_like_profile(self.doctor, 'D-GDEFER')
        StaffProfile.objects.filter(user=self.doctor).update(
            allowed_clinical_modules=[MODULE_APPOINTMENTS],
        )
        consult, _ = AppointmentTypeDefault.objects.update_or_create(
            appointment_type='consultation',
            defaults={'is_active': True},
        )
        consult.assigned_doctors.set([self.doctor])

        appt_date = timezone.now().date() + timedelta(days=7)
        while appt_date.weekday() >= 5:
            appt_date += timedelta(days=1)
        self.appt_date = appt_date

    def _guest_count(self):
        return User.objects.filter(email__iendswith=f'@{GUEST_EMAIL_DOMAIN}').count()

    def test_failed_schedule_does_not_create_guest(self):
        weekend = timezone.localdate()
        while weekend.weekday() < 5:
            weekend += timedelta(days=1)
        before = self._guest_count()
        self.client.force_login(self.doctor)
        response = self.client.post(
            reverse('appointments:schedule_for_patient'),
            {
                'register_guest': '1',
                'guest_first_name': 'Walk',
                'guest_last_name': 'In',
                'guest_email': 'walkin@example.com',
                'appointment_type': 'consultation',
                'date': weekend.isoformat(),
                'time': '09:00',
                'reason': 'Should not create guest',
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'not available on weekends')
        self.assertEqual(self._guest_count(), before)
        self.assertFalse(Appointment.objects.filter(reason='Should not create guest').exists())

    def test_guest_created_only_when_appointment_is_booked(self):
        before = self._guest_count()
        self.client.force_login(self.doctor)
        response = self.client.post(
            reverse('appointments:schedule_for_patient'),
            {
                'register_guest': '1',
                'guest_first_name': 'Walk',
                'guest_last_name': 'In',
                'guest_email': 'walkin-book@example.com',
                'appointment_type': 'consultation',
                'date': self.appt_date.isoformat(),
                'time': '09:00',
                'reason': 'Guest booking',
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self._guest_count(), before + 1)
        guest = User.objects.get(first_name='Walk', last_name='In')
        self.assertTrue(is_guest_user(guest))
        self.assertEqual(guest.patient_profile.contact_email, 'walkin-book@example.com')
        appointment = Appointment.objects.get(patient=guest, date=self.appt_date, time=time(9, 0))
        self.assertEqual(appointment.doctor_id, self.doctor.id)
        self.assertEqual(appointment.status, 'confirmed')


