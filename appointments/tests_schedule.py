import json
from datetime import datetime, timedelta

from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from appointments.models import AppointmentTypeDefault
from appointments.views import _get_schedule_context
from core.models import PatientProfile, StaffProfile, User


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
