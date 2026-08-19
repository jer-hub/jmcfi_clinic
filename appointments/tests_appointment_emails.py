"""Integration tests for appointment status update and self-schedule emails."""

from datetime import time, timedelta

from django.conf import settings
from django.core import mail
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from appointments.models import Appointment, AppointmentTypeDefault
from core.doctor_access import MODULE_APPOINTMENTS
from core.models import ClinicSettings, PatientProfile, StaffProfile, User
from core.settings_service import invalidate_settings_cache
from core.tests import _complete_staff_like_profile


def _weekday_on_or_after(start, days_ahead=7):
    candidate = start + timedelta(days=days_ahead)
    while candidate.weekday() >= 5:
        candidate += timedelta(days=1)
    return candidate


def _enable_clinic_email():
    ClinicSettings.load()
    ClinicSettings.objects.filter(pk=ClinicSettings.SINGLETON_PK).update(
        enable_email_notifications=True,
    )
    invalidate_settings_cache()


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    MIDDLEWARE=[
        middleware
        for middleware in settings.MIDDLEWARE
        if middleware != 'core.middleware.ProfileCompleteMiddleware'
    ],
)
class AppointmentStatusUpdateEmailTests(TestCase):
    def setUp(self):
        _enable_clinic_email()
        self.client = Client()

        self.admin = User.objects.create_user(
            email='appt-email-admin@test.com',
            password='pass1234',
            role='admin',
            is_staff=True,
            first_name='Appt',
            last_name='Admin',
        )
        _complete_staff_like_profile(self.admin, 'ADM-APPT-EMAIL')

        self.doctor = User.objects.create_user(
            email='appt-email-doc@test.com',
            password='pass1234',
            role='doctor',
            first_name='Appt',
            last_name='Doctor',
        )
        _complete_staff_like_profile(self.doctor, 'DOC-APPT-EMAIL')
        StaffProfile.objects.filter(user=self.doctor).update(
            license_number='LIC-AE',
            ptr_no='PTR-AE',
            allowed_clinical_modules=[MODULE_APPOINTMENTS],
        )

        self.patient = User.objects.create_user(
            email='appt-email-patient@test.com',
            password='pass1234',
            role='patient',
            first_name='Appt',
            last_name='Patient',
        )
        profile, _ = PatientProfile.objects.get_or_create(user=self.patient)
        profile.patient_id = 'P-APPT-EMAIL'
        profile.date_of_birth = '2004-01-01'
        profile.phone = '09111111111'
        profile.emergency_contact = 'Parent'
        profile.emergency_phone = '09222222222'
        profile.blood_type = 'O+'
        profile.save()

        default, _ = AppointmentTypeDefault.objects.update_or_create(
            appointment_type='consultation',
            defaults={'is_active': True},
        )
        default.assigned_doctors.set([self.doctor])

        self.appt_date = _weekday_on_or_after(timezone.now().date())
        self.appointment = Appointment.objects.create(
            patient=self.patient,
            doctor=self.doctor,
            appointment_type='consultation',
            date=self.appt_date,
            time=time(10, 0),
            reason='Status update email test',
            status='pending',
        )

    def test_doctor_status_update_sends_templated_update_email(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse('appointments:appointment_detail', args=[self.appointment.id]),
            {'status': 'confirmed'},
        )
        self.assertEqual(response.status_code, 302)
        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.status, 'confirmed')
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ['appt-email-patient@test.com'])
        self.assertIn('confirmed', message.body.lower())
        self.assertIn(self.appt_date.strftime('%B'), message.body)
        self.assertIn(f'/appointments/{self.appointment.pk}/', message.body)
        html_parts = [alt[0] for alt in message.alternatives if alt[1] == 'text/html']
        self.assertTrue(html_parts)
        self.assertIn('View appointment details', html_parts[0])

    def test_status_update_email_not_duplicate_plain_text(self):
        self.client.force_login(self.admin)
        self.client.post(
            reverse('appointments:appointment_detail', args=[self.appointment.id]),
            {'status': 'missed'},
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('missed', mail.outbox[0].body.lower())
        self.assertNotIn(
            'Your appointment status has been updated to',
            mail.outbox[0].body,
        )

    def test_patient_self_schedule_sends_confirmation_email(self):
        mail.outbox.clear()
        self.client.force_login(self.patient)
        book_date = _weekday_on_or_after(self.appt_date, days_ahead=14)
        response = self.client.post(
            reverse('appointments:schedule_appointment'),
            {
                'doctor': self.doctor.id,
                'appointment_type': 'consultation',
                'date': book_date.isoformat(),
                'time': '11:00',
                'reason': 'Self-booked visit',
            },
        )
        self.assertEqual(response.status_code, 302)
        patient_messages = [
            message for message in mail.outbox
            if message.to == ['appt-email-patient@test.com']
        ]
        doctor_messages = [
            message for message in mail.outbox
            if message.to == ['appt-email-doc@test.com']
        ]
        self.assertEqual(len(patient_messages), 1)
        self.assertIn('scheduled', patient_messages[0].body.lower())
        self.assertEqual(len(doctor_messages), 1)
        self.assertIn('Self-booked visit', doctor_messages[0].body)
        self.assertIn('Appt Patient', doctor_messages[0].body)
        appointment = Appointment.objects.get(
            patient=self.patient,
            date=book_date,
            time=time(11, 0),
        )
        self.assertIn(f'/appointments/{appointment.pk}/', doctor_messages[0].body)
        self.assertNotIn(
            'New appointment request from',
            doctor_messages[0].body,
        )

    def test_doctor_confirms_sends_patient_templated_email(self):
        mail.outbox.clear()
        self.client.force_login(self.doctor)
        response = self.client.post(
            reverse('appointments:appointment_detail', args=[self.appointment.id]),
            {'status': 'confirmed'},
        )
        self.assertEqual(response.status_code, 302)
        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.status, 'confirmed')
        patient_messages = [
            message for message in mail.outbox
            if message.to == ['appt-email-patient@test.com']
        ]
        self.assertEqual(len(patient_messages), 1)
        self.assertIn('confirmed', patient_messages[0].body.lower())
        self.assertIn(f'/appointments/{self.appointment.pk}/', patient_messages[0].body)
        self.assertIn('Status update email test', patient_messages[0].body)
        self.assertIn('Appt Doctor', patient_messages[0].body)

    def test_doctor_cancels_sends_patient_templated_email(self):
        mail.outbox.clear()
        self.client.force_login(self.doctor)
        response = self.client.post(
            reverse('appointments:appointment_detail', args=[self.appointment.id]),
            {'status': 'cancelled'},
        )
        self.assertEqual(response.status_code, 302)
        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.status, 'cancelled')
        patient_messages = [
            message for message in mail.outbox
            if message.to == ['appt-email-patient@test.com']
        ]
        doctor_messages = [
            message for message in mail.outbox
            if message.to == ['appt-email-doc@test.com']
        ]
        self.assertEqual(len(patient_messages), 1)
        self.assertIn('cancelled', patient_messages[0].body.lower())
        self.assertIn(f'/appointments/{self.appointment.pk}/', patient_messages[0].body)
        self.assertEqual(len(doctor_messages), 0)

    def test_patient_cancel_sends_doctor_templated_email(self):
        mail.outbox.clear()
        self.client.force_login(self.patient)
        response = self.client.post(
            reverse('appointments:appointment_detail', args=[self.appointment.id]),
            {'status': 'cancelled'},
        )
        self.assertEqual(response.status_code, 302)
        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.status, 'cancelled')
        doctor_messages = [
            message for message in mail.outbox
            if message.to == ['appt-email-doc@test.com']
        ]
        self.assertEqual(len(doctor_messages), 1)
        self.assertIn('cancelled', doctor_messages[0].body.lower())
        self.assertIn(f'/appointments/{self.appointment.pk}/', doctor_messages[0].body)
        self.assertIn('Appt Patient', doctor_messages[0].body)
        self.assertIn('Status update email test', doctor_messages[0].body)
        self.assertNotIn(
            'Appointment with Appt Patient has been cancelled',
            doctor_messages[0].body,
        )
        patient_messages = [
            message for message in mail.outbox
            if message.to == ['appt-email-patient@test.com']
        ]
        self.assertEqual(len(patient_messages), 0)
