import json
from datetime import date, datetime, time, timedelta

from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from appointments.models import Appointment, AppointmentTypeDefault
from core.models import PatientProfile, StaffProfile, User


def _weekday_on_or_after(start: date, days_ahead: int = 7) -> date:
    candidate = start + timedelta(days=days_ahead)
    while candidate.weekday() >= 5:
        candidate += timedelta(days=1)
    return candidate


@override_settings(
    MIDDLEWARE=[
        middleware
        for middleware in settings.MIDDLEWARE
        if middleware != 'core.middleware.ProfileCompleteMiddleware'
    ]
)
class StaffClinicalPermissionsTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            email='staff-perm@test.com',
            password='pass1234',
            role='staff',
            first_name='Clinic',
            last_name='Staff',
        )
        StaffProfile.objects.update_or_create(
            user=self.staff,
            defaults={
                'staff_id': 'STF-PERM',
                'department': 'Front Desk',
                'phone': '09123456789',
            },
        )

        self.doctor = User.objects.create_user(
            email='doctor-perm@test.com',
            password='pass1234',
            role='doctor',
            first_name='Assigned',
            last_name='Doctor',
        )
        StaffProfile.objects.update_or_create(
            user=self.doctor,
            defaults={
                'staff_id': 'DOC-PERM',
                'department': 'General',
                'phone': '09222222222',
                'license_number': 'LIC-P',
                'ptr_no': 'PTR-P',
            },
        )

        self.other_doctor = User.objects.create_user(
            email='other-doc-perm@test.com',
            password='pass1234',
            role='doctor',
            first_name='Other',
            last_name='Doctor',
        )
        StaffProfile.objects.update_or_create(
            user=self.other_doctor,
            defaults={
                'staff_id': 'DOC-OTHER',
                'department': 'Dental',
                'phone': '09333333333',
                'license_number': 'LIC-O',
                'ptr_no': 'PTR-O',
            },
        )

        self.patient = User.objects.create_user(
            email='patient-perm@test.com',
            password='pass1234',
            role='patient',
            first_name='Test',
            last_name='Patient',
        )
        profile, _ = PatientProfile.objects.get_or_create(user=self.patient)
        profile.patient_id = 'P-PERM-001'
        profile.date_of_birth = '2004-01-01'
        profile.phone = '09444444444'
        profile.emergency_contact = 'Parent'
        profile.emergency_phone = '09555555555'
        profile.blood_type = 'A+'
        profile.save()

        self.consult_default, _ = AppointmentTypeDefault.objects.update_or_create(
            appointment_type='consultation',
            defaults={'is_active': True},
        )
        self.consult_default.assigned_doctors.set([self.doctor])

        self.appt_date = _weekday_on_or_after(timezone.now().date())

        self.doctor_appointment = Appointment.objects.create(
            patient=self.patient,
            doctor=self.doctor,
            appointment_type='consultation',
            date=self.appt_date,
            time=time(9, 0),
            reason='Doctor visit',
            status='pending',
        )

    def test_staff_sees_clinic_wide_appointment_list(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse('appointments:appointment_list'))
        self.assertEqual(response.status_code, 200)
        appointment_ids = {appt.id for appt in response.context['appointments']}
        self.assertIn(self.doctor_appointment.id, appointment_ids)

    def test_staff_cannot_post_appointment_status_update(self):
        self.client.force_login(self.staff)
        response = self.client.post(
            reverse('appointments:appointment_detail', args=[self.doctor_appointment.id]),
            {'status': 'confirmed', 'notes': 'Staff attempt'},
        )
        self.assertEqual(response.status_code, 302)
        self.doctor_appointment.refresh_from_db()
        self.assertEqual(self.doctor_appointment.status, 'pending')

    def test_staff_can_view_any_appointment_detail(self):
        self.client.force_login(self.staff)
        response = self.client.get(
            reverse('appointments:appointment_detail', args=[self.doctor_appointment.id])
        )
        self.assertEqual(response.status_code, 200)

    def test_staff_schedule_for_patient_requires_doctor(self):
        self.client.force_login(self.staff)
        response = self.client.post(
            reverse('appointments:schedule_for_patient'),
            {
                'patient': self.patient.id,
                'appointment_type': 'consultation',
                'date': self.appt_date.isoformat(),
                'time': '10:00',
                'reason': 'Follow-up',
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            Appointment.objects.filter(
                patient=self.patient,
                date=self.appt_date,
                time=time(10, 0),
            ).exists()
        )

    def test_staff_schedule_for_patient_with_assigned_doctor(self):
        self.client.force_login(self.staff)
        response = self.client.post(
            reverse('appointments:schedule_for_patient'),
            {
                'patient': self.patient.id,
                'doctor': self.doctor.id,
                'appointment_type': 'consultation',
                'date': self.appt_date.isoformat(),
                'time': '10:00',
                'reason': 'Staff booked follow-up',
            },
        )
        self.assertEqual(response.status_code, 302)
        appointment = Appointment.objects.get(
            patient=self.patient,
            date=self.appt_date,
            time=time(10, 0),
        )
        self.assertEqual(appointment.doctor_id, self.doctor.id)
        self.assertEqual(appointment.status, 'confirmed')

    def test_staff_schedule_rejects_unassigned_doctor(self):
        self.client.force_login(self.staff)
        response = self.client.post(
            reverse('appointments:schedule_for_patient'),
            {
                'patient': self.patient.id,
                'doctor': self.other_doctor.id,
                'appointment_type': 'consultation',
                'date': self.appt_date.isoformat(),
                'time': '11:00',
                'reason': 'Wrong doctor',
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            Appointment.objects.filter(
                patient=self.patient,
                date=self.appt_date,
                time=time(11, 0),
            ).exists()
        )

    def test_staff_schedule_page_includes_doctor_picker(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse('appointments:schedule_for_patient'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="doctor"')
        type_map = json.loads(response.context['type_doctor_map'])
        self.assertEqual(type_map['consultation'], [self.doctor.id])

    def test_doctor_schedule_for_patient_still_books_as_self(self):
        self.client.force_login(self.doctor)
        response = self.client.post(
            reverse('appointments:schedule_for_patient'),
            {
                'patient': self.patient.id,
                'appointment_type': 'consultation',
                'date': self.appt_date.isoformat(),
                'time': '14:00',
                'reason': 'Doctor booked',
            },
        )
        self.assertEqual(response.status_code, 302)
        appointment = Appointment.objects.get(
            patient=self.patient,
            date=self.appt_date,
            time=time(14, 0),
        )
        self.assertEqual(appointment.doctor_id, self.doctor.id)
