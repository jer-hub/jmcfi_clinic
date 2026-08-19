"""Tests for guest contact email, tokens, magic-link access, and cancel."""

from datetime import date, time, timedelta

from django.conf import settings
from django.core import mail
from django.test import Client, RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from appointments.models import Appointment
from core.guest_access import (
	build_guest_url,
	issue_guest_access_token,
	validate_guest_token,
)
from core.guest_auth import (
	create_guest_user,
	is_guest_user,
	resolve_patient_contact_email,
)
from core.guest_emails import (
	email_guest_appointment_scheduled,
	email_guest_health_form_pending,
)
from core.models import ClinicSettings, GuestAccessToken, User
from core.notification_delivery import send_notification_email
from core.settings_service import invalidate_settings_cache
from core.tests import _complete_staff_like_profile
from health_forms_services.models import HealthProfileForm

_TEST_MIDDLEWARE = [
	m for m in settings.MIDDLEWARE if m != 'core.middleware.ProfileCompleteMiddleware'
]


def _enable_clinic_email():
	ClinicSettings.load()
	ClinicSettings.objects.filter(pk=ClinicSettings.SINGLETON_PK).update(
		enable_email_notifications=True,
	)
	invalidate_settings_cache()


@override_settings(
	EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
	MIDDLEWARE=_TEST_MIDDLEWARE,
)
class GuestContactEmailTests(TestCase):
	def test_create_guest_stores_contact_email(self):
		user = create_guest_user(
			first_name='Ana',
			last_name='Reyes',
			contact_email='ana@example.com',
		)
		self.assertTrue(is_guest_user(user))
		self.assertEqual(user.patient_profile.contact_email, 'ana@example.com')
		self.assertEqual(resolve_patient_contact_email(user), 'ana@example.com')

	def test_resolve_patient_contact_email_for_regular_patient(self):
		user = User.objects.create_user(
			email='patient@example.com',
			password='Pass123!',
			role='patient',
			is_active=True,
		)
		self.assertEqual(resolve_patient_contact_email(user), 'patient@example.com')

	def test_send_notification_email_uses_contact_email(self):
		_enable_clinic_email()
		user = create_guest_user(contact_email='guest-notify@example.com')
		ok = send_notification_email(user, 'Hello', 'Body text')
		self.assertTrue(ok)
		self.assertEqual(len(mail.outbox), 1)
		self.assertEqual(mail.outbox[0].to, ['guest-notify@example.com'])
		self.assertNotIn('@guest.local', mail.outbox[0].to[0])


class GuestAccessTokenTests(TestCase):
	def test_issue_and_validate_token(self):
		user = create_guest_user(contact_email='a@example.com')
		token, raw = issue_guest_access_token(
			user, GuestAccessToken.Purpose.APPOINTMENT, 42
		)
		self.assertTrue(token.token_hash)
		found = validate_guest_token(raw, GuestAccessToken.Purpose.APPOINTMENT)
		self.assertIsNotNone(found)
		self.assertEqual(found.pk, token.pk)
		self.assertEqual(found.object_id, 42)

	def test_wrong_purpose_rejected(self):
		user = create_guest_user(contact_email='a@example.com')
		_, raw = issue_guest_access_token(
			user, GuestAccessToken.Purpose.APPOINTMENT, 1
		)
		self.assertIsNone(validate_guest_token(raw, GuestAccessToken.Purpose.HEALTH_FORM))

	def test_expired_token_rejected(self):
		user = create_guest_user(contact_email='a@example.com')
		token, raw = issue_guest_access_token(
			user, GuestAccessToken.Purpose.HEALTH_FORM, 9
		)
		GuestAccessToken.objects.filter(pk=token.pk).update(
			expires_at=timezone.now() - timedelta(hours=1),
		)
		self.assertIsNone(validate_guest_token(raw, GuestAccessToken.Purpose.HEALTH_FORM))

	def test_reissue_revokes_prior(self):
		user = create_guest_user(contact_email='a@example.com')
		first, raw1 = issue_guest_access_token(
			user, GuestAccessToken.Purpose.APPOINTMENT, 5
		)
		second, raw2 = issue_guest_access_token(
			user, GuestAccessToken.Purpose.APPOINTMENT, 5
		)
		first.refresh_from_db()
		self.assertIsNotNone(first.revoked_at)
		self.assertIsNone(validate_guest_token(raw1, GuestAccessToken.Purpose.APPOINTMENT))
		self.assertEqual(
			validate_guest_token(raw2, GuestAccessToken.Purpose.APPOINTMENT).pk,
			second.pk,
		)

	def test_build_guest_url(self):
		factory = RequestFactory()
		request = factory.get('/')
		url = build_guest_url(request, GuestAccessToken.Purpose.APPOINTMENT, 'abc123')
		self.assertIn('/guest/appointment/abc123/', url)


@override_settings(
	EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
	MIDDLEWARE=_TEST_MIDDLEWARE,
)
class GuestViewsAndEmailHooksTests(TestCase):
	def setUp(self):
		_enable_clinic_email()
		self.doctor = User.objects.create_user(
			email='doc-guest@test.com',
			password='DoctorPass123!',
			role='doctor',
			is_staff=True,
			is_active=True,
			first_name='Doc',
			last_name='Tor',
		)
		_complete_staff_like_profile(self.doctor, 'DOC-GUEST-001')
		self.guest = create_guest_user(
			first_name='Guest',
			last_name='Patient',
			contact_email='guest-patient@example.com',
		)
		self.client = Client()

	def test_guest_appointment_view(self):
		appointment = Appointment.objects.create(
			patient=self.guest,
			doctor=self.doctor,
			appointment_type='consultation',
			date=date.today() + timedelta(days=3),
			time=time(10, 0),
			reason='Checkup',
			status='confirmed',
		)
		_, raw = issue_guest_access_token(
			self.guest, GuestAccessToken.Purpose.APPOINTMENT, appointment.pk
		)
		response = self.client.get(
			reverse('core:guest_appointment', kwargs={'token': raw})
		)
		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Checkup')
		self.assertContains(response, 'Your appointment')
		self.assertContains(response, 'Cancel appointment')

	def test_guest_appointment_cancel(self):
		ClinicSettings.load()
		ClinicSettings.objects.filter(pk=ClinicSettings.SINGLETON_PK).update(
			cancellation_cutoff_hours=1,
		)
		invalidate_settings_cache()
		appointment = Appointment.objects.create(
			patient=self.guest,
			doctor=self.doctor,
			appointment_type='consultation',
			date=date.today() + timedelta(days=5),
			time=time(10, 0),
			reason='Checkup',
			status='confirmed',
		)
		token, raw = issue_guest_access_token(
			self.guest, GuestAccessToken.Purpose.APPOINTMENT, appointment.pk
		)
		url = reverse('core:guest_appointment', kwargs={'token': raw})
		response = self.client.post(url, {'action': 'cancel'})
		self.assertEqual(response.status_code, 200)
		appointment.refresh_from_db()
		self.assertEqual(appointment.status, 'cancelled')
		token.refresh_from_db()
		self.assertIsNotNone(token.revoked_at)
		self.assertContains(response, 'cancelled')
		self.assertEqual(len(mail.outbox), 1)
		self.assertEqual(mail.outbox[0].to, ['doc-guest@test.com'])
		self.assertIn('cancelled', mail.outbox[0].body.lower())
		self.assertIn(f'/appointments/{appointment.pk}/', mail.outbox[0].body)
		self.assertIn('Checkup', mail.outbox[0].body)

	def test_guest_appointment_cancel_blocked_by_cutoff(self):
		ClinicSettings.load()
		ClinicSettings.objects.filter(pk=ClinicSettings.SINGLETON_PK).update(
			cancellation_cutoff_hours=48,
		)
		invalidate_settings_cache()
		appointment = Appointment.objects.create(
			patient=self.guest,
			doctor=self.doctor,
			appointment_type='consultation',
			date=date.today() + timedelta(days=1),
			time=time(10, 0),
			reason='Soon',
			status='confirmed',
		)
		_, raw = issue_guest_access_token(
			self.guest, GuestAccessToken.Purpose.APPOINTMENT, appointment.pk
		)
		url = reverse('core:guest_appointment', kwargs={'token': raw})
		response = self.client.post(url, {'action': 'cancel'})
		self.assertEqual(response.status_code, 200)
		appointment.refresh_from_db()
		self.assertEqual(appointment.status, 'confirmed')

	def test_guest_health_form_view_and_submit(self):
		health_form = HealthProfileForm.objects.create(
			user=self.guest,
			status=HealthProfileForm.Status.INCOMPLETE,
			first_name='Guest',
			last_name='Patient',
			email_address='guest-patient@example.com',
			date_of_birth=date(2000, 1, 1),
			gender='female',
			designation='guest',
			mobile_number='+639171234567',
		)
		_, raw = issue_guest_access_token(
			self.guest,
			GuestAccessToken.Purpose.HEALTH_FORM,
			health_form.pk,
			created_by=self.doctor,
		)
		url = reverse('core:guest_health_form', kwargs={'token': raw})
		get_resp = self.client.get(url)
		self.assertEqual(get_resp.status_code, 200)
		self.assertContains(get_resp, 'Complete your health profile')
		self.assertContains(get_resp, 'Cancel draft')

		submit = self.client.post(url, {'action': 'submit', 'section': 'personal'})
		self.assertEqual(submit.status_code, 200)
		health_form.refresh_from_db()
		self.assertEqual(health_form.status, HealthProfileForm.Status.PENDING)
		from core.models import Notification

		notif = Notification.objects.filter(
			user=self.doctor,
			related_id=health_form.pk,
			transaction_type='health_form_submitted',
		).first()
		self.assertIsNotNone(notif)
		self.assertIn('submitted', notif.title.lower())

	def test_guest_health_form_cancel(self):
		health_form = HealthProfileForm.objects.create(
			user=self.guest,
			status=HealthProfileForm.Status.INCOMPLETE,
			first_name='Guest',
			last_name='Patient',
			email_address='guest-patient@example.com',
		)
		token, raw = issue_guest_access_token(
			self.guest, GuestAccessToken.Purpose.HEALTH_FORM, health_form.pk
		)
		url = reverse('core:guest_health_form', kwargs={'token': raw})
		response = self.client.post(url, {'action': 'cancel', 'section': 'personal'})
		self.assertEqual(response.status_code, 200)
		health_form.refresh_from_db()
		self.assertEqual(health_form.status, HealthProfileForm.Status.CANCELLED)
		token.refresh_from_db()
		self.assertIsNotNone(token.revoked_at)
		# Revoked token cannot reopen edit
		again = self.client.get(url)
		self.assertEqual(again.status_code, 404)

	def test_guest_health_form_cancel_rejected_when_pending(self):
		health_form = HealthProfileForm.objects.create(
			user=self.guest,
			status=HealthProfileForm.Status.PENDING,
			first_name='Guest',
			last_name='Patient',
		)
		_, raw = issue_guest_access_token(
			self.guest, GuestAccessToken.Purpose.HEALTH_FORM, health_form.pk
		)
		url = reverse('core:guest_health_form', kwargs={'token': raw})
		response = self.client.post(url, {'action': 'cancel', 'section': 'personal'})
		self.assertEqual(response.status_code, 200)
		health_form.refresh_from_db()
		self.assertEqual(health_form.status, HealthProfileForm.Status.PENDING)
		self.assertContains(response, 'no longer open')

	def test_email_guest_appointment_scheduled(self):
		appointment = Appointment.objects.create(
			patient=self.guest,
			doctor=self.doctor,
			appointment_type='consultation',
			date=date.today() + timedelta(days=2),
			time=time(9, 0),
			reason='Follow-up',
			status='confirmed',
		)
		factory = RequestFactory()
		request = factory.get('/')
		ok = email_guest_appointment_scheduled(request, appointment, created_by=self.doctor)
		self.assertTrue(ok)
		self.assertEqual(len(mail.outbox), 1)
		self.assertEqual(mail.outbox[0].to, ['guest-patient@example.com'])
		self.assertIn('/guest/appointment/', mail.outbox[0].body)
		self.assertIn('cancel', mail.outbox[0].body.lower())

	def test_email_patient_appointment_scheduled(self):
		from core.guest_emails import email_patient_appointment_scheduled
		from core.models import PatientProfile

		patient = User.objects.create_user(
			email='existing-patient@example.com',
			password='Pass123!',
			role='patient',
			is_active=True,
			first_name='Existing',
			last_name='Patient',
		)
		PatientProfile.objects.update_or_create(
			user=patient,
			defaults={'patient_id': 'P-EMAIL-001'},
		)
		appointment = Appointment.objects.create(
			patient=patient,
			doctor=self.doctor,
			appointment_type='consultation',
			date=date.today() + timedelta(days=2),
			time=time(11, 0),
			reason='Annual check',
			status='confirmed',
		)
		factory = RequestFactory()
		request = factory.get('/')
		ok = email_patient_appointment_scheduled(request, appointment)
		self.assertTrue(ok)
		self.assertEqual(len(mail.outbox), 1)
		self.assertEqual(mail.outbox[0].to, ['existing-patient@example.com'])
		self.assertIn(f'/appointments/{appointment.pk}/', mail.outbox[0].body)
		self.assertNotIn('/guest/appointment/', mail.outbox[0].body)
		self.assertIn('sign in', mail.outbox[0].body.lower())

	def test_email_doctor_new_appointment_request(self):
		from core.guest_emails import email_doctor_new_appointment_request
		from core.models import PatientProfile

		patient = User.objects.create_user(
			email='booking-patient@example.com',
			password='Pass123!',
			role='patient',
			is_active=True,
			first_name='Booking',
			last_name='Patient',
		)
		PatientProfile.objects.update_or_create(
			user=patient,
			defaults={'patient_id': 'P-EMAIL-BOOK'},
		)
		appointment = Appointment.objects.create(
			patient=patient,
			doctor=self.doctor,
			appointment_type='consultation',
			date=date.today() + timedelta(days=3),
			time=time(15, 0),
			reason='Self-booked checkup',
			status='pending',
		)
		factory = RequestFactory()
		request = factory.get('/')
		ok = email_doctor_new_appointment_request(request, appointment)
		self.assertTrue(ok)
		self.assertEqual(len(mail.outbox), 1)
		self.assertEqual(mail.outbox[0].to, ['doc-guest@test.com'])
		self.assertIn(f'/appointments/{appointment.pk}/', mail.outbox[0].body)
		self.assertIn('Booking Patient', mail.outbox[0].body)
		self.assertIn('Self-booked checkup', mail.outbox[0].body)
		html_parts = [alt[0] for alt in mail.outbox[0].alternatives if alt[1] == 'text/html']
		self.assertIn('View appointment details', html_parts[0])

	def test_email_doctor_appointment_cancelled(self):
		from core.guest_emails import email_doctor_appointment_cancelled
		from core.models import PatientProfile

		patient = User.objects.create_user(
			email='cancel-booking@example.com',
			password='Pass123!',
			role='patient',
			is_active=True,
			first_name='Cancel',
			last_name='Booking',
		)
		PatientProfile.objects.update_or_create(
			user=patient,
			defaults={'patient_id': 'P-EMAIL-CANCEL-DOC'},
		)
		appointment = Appointment.objects.create(
			patient=patient,
			doctor=self.doctor,
			appointment_type='consultation',
			date=date.today() + timedelta(days=3),
			time=time(16, 0),
			reason='Will cancel',
			status='cancelled',
			notes='Patient called ahead.',
		)
		factory = RequestFactory()
		request = factory.get('/')
		ok = email_doctor_appointment_cancelled(
			request,
			appointment,
			cancelled_by=patient,
		)
		self.assertTrue(ok)
		self.assertEqual(len(mail.outbox), 1)
		self.assertEqual(mail.outbox[0].to, ['doc-guest@test.com'])
		self.assertIn('cancelled', mail.outbox[0].body.lower())
		self.assertIn(f'/appointments/{appointment.pk}/', mail.outbox[0].body)
		self.assertIn('Cancel Booking', mail.outbox[0].body)
		self.assertIn('Patient called ahead.', mail.outbox[0].body)
		self.assertIn('Cancelled by: Cancel Booking', mail.outbox[0].body)

	def test_email_guest_appointment_updated_confirmed(self):
		from core.guest_emails import email_guest_appointment_updated

		appointment = Appointment.objects.create(
			patient=self.guest,
			doctor=self.doctor,
			appointment_type='consultation',
			date=date.today() + timedelta(days=2),
			time=time(9, 30),
			reason='Follow-up',
			status='confirmed',
		)
		factory = RequestFactory()
		request = factory.get('/')
		ok = email_guest_appointment_updated(
			request,
			appointment,
			previous_status='pending',
			created_by=self.doctor,
		)
		self.assertTrue(ok)
		self.assertEqual(len(mail.outbox), 1)
		self.assertEqual(mail.outbox[0].to, ['guest-patient@example.com'])
		self.assertIn('/guest/appointment/', mail.outbox[0].body)
		self.assertIn('confirmed', mail.outbox[0].body.lower())
		self.assertIn('Previous status: Pending', mail.outbox[0].body)

	def test_email_patient_appointment_updated_cancelled(self):
		from core.guest_emails import email_patient_appointment_updated
		from core.models import PatientProfile

		patient = User.objects.create_user(
			email='cancel-patient@example.com',
			password='Pass123!',
			role='patient',
			is_active=True,
			first_name='Cancel',
			last_name='Patient',
		)
		PatientProfile.objects.update_or_create(
			user=patient,
			defaults={'patient_id': 'P-EMAIL-CANCEL'},
		)
		appointment = Appointment.objects.create(
			patient=patient,
			doctor=self.doctor,
			appointment_type='consultation',
			date=date.today() + timedelta(days=4),
			time=time(14, 0),
			reason='Routine visit',
			status='cancelled',
		)
		factory = RequestFactory()
		request = factory.get('/')
		ok = email_patient_appointment_updated(
			request,
			appointment,
			previous_status='confirmed',
		)
		self.assertTrue(ok)
		self.assertEqual(len(mail.outbox), 1)
		self.assertEqual(mail.outbox[0].to, ['cancel-patient@example.com'])
		self.assertIn(f'/appointments/{appointment.pk}/', mail.outbox[0].body)
		self.assertIn('cancelled', mail.outbox[0].body.lower())

	def test_email_appointment_updated_skips_when_no_contact(self):
		from core.guest_emails import email_appointment_updated

		guest_no_email = create_guest_user(
			first_name='No',
			last_name='Email',
			contact_email='',
		)
		guest_no_email.patient_profile.contact_email = ''
		guest_no_email.patient_profile.save(update_fields=['contact_email'])
		appointment = Appointment.objects.create(
			patient=guest_no_email,
			doctor=self.doctor,
			appointment_type='consultation',
			date=date.today() + timedelta(days=1),
			time=time(8, 0),
			reason='Walk-in',
			status='confirmed',
		)
		factory = RequestFactory()
		request = factory.get('/')
		ok = email_appointment_updated(
			request,
			appointment,
			previous_status='pending',
			created_by=self.doctor,
		)
		self.assertFalse(ok)
		self.assertEqual(len(mail.outbox), 0)

	def test_email_patient_appointment_results_ready(self):
		from core.guest_emails import email_patient_appointment_results_ready
		from core.models import PatientProfile
		from medical_records.models import MedicalRecord

		patient = User.objects.create_user(
			email='results-patient@example.com',
			password='Pass123!',
			role='patient',
			is_active=True,
			first_name='Results',
			last_name='Patient',
		)
		PatientProfile.objects.update_or_create(
			user=patient,
			defaults={'patient_id': 'P-EMAIL-002'},
		)
		appointment = Appointment.objects.create(
			patient=patient,
			doctor=self.doctor,
			appointment_type='consultation',
			date=date.today() - timedelta(days=1),
			time=time(9, 0),
			reason='Visit',
			status='completed',
		)
		record = MedicalRecord.objects.create(
			patient=patient,
			doctor=self.doctor,
			appointment=appointment,
			diagnosis='Mild fever',
			treatment='Rest',
		)
		factory = RequestFactory()
		request = factory.get('/')
		ok = email_patient_appointment_results_ready(request, appointment)
		self.assertTrue(ok)
		self.assertEqual(len(mail.outbox), 1)
		self.assertEqual(mail.outbox[0].to, ['results-patient@example.com'])
		self.assertIn(f'/medical-records/{record.pk}/', mail.outbox[0].body)
		self.assertIn('results', mail.outbox[0].body.lower())
		self.assertIn('sign in', mail.outbox[0].body.lower())

	def test_email_guest_medical_record_results_ready(self):
		from core.guest_emails import email_guest_medical_record_results_ready
		from medical_records.models import MedicalRecord

		appointment = Appointment.objects.create(
			patient=self.guest,
			doctor=self.doctor,
			appointment_type='consultation',
			date=date.today() - timedelta(days=1),
			time=time(10, 0),
			reason='Checkup',
			status='completed',
		)
		record = MedicalRecord.objects.create(
			patient=self.guest,
			doctor=self.doctor,
			appointment=appointment,
			diagnosis='Mild fever',
			treatment='Rest and fluids',
			lab_results='CBC normal',
			vital_signs={'temperature': '37.2', 'blood_pressure': '120/80'},
		)
		factory = RequestFactory()
		request = factory.get('/')
		ok = email_guest_medical_record_results_ready(
			request, record, created_by=self.doctor
		)
		self.assertTrue(ok)
		self.assertEqual(len(mail.outbox), 1)
		self.assertEqual(mail.outbox[0].to, ['guest-patient@example.com'])
		self.assertIn('/guest/medical-record/', mail.outbox[0].body)
		self.assertNotIn('/medical-records/', mail.outbox[0].body)
		self.assertIn('medical record', mail.outbox[0].body.lower())

		raw = None
		token = GuestAccessToken.objects.filter(
			purpose=GuestAccessToken.Purpose.MEDICAL_RECORD,
			object_id=record.pk,
			revoked_at__isnull=True,
		).first()
		self.assertIsNotNone(token)
		# Re-issue to capture raw for view test via email body is fragile; validate view separately.
		_, raw = issue_guest_access_token(
			self.guest,
			GuestAccessToken.Purpose.MEDICAL_RECORD,
			record.pk,
			created_by=self.doctor,
		)
		url = reverse('core:guest_medical_record', kwargs={'token': raw})
		response = self.client.get(url)
		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Your medical record')
		self.assertContains(response, 'Mild fever')
		self.assertContains(response, 'Rest and fluids')
		self.assertContains(response, 'CBC normal')

	def test_email_patient_medical_record_results_ready(self):
		from core.guest_emails import email_patient_medical_record_results_ready
		from core.models import PatientProfile
		from medical_records.models import MedicalRecord

		patient = User.objects.create_user(
			email='mr-results-patient@example.com',
			password='Pass123!',
			role='patient',
			is_active=True,
			first_name='Results',
			last_name='Patient',
		)
		PatientProfile.objects.update_or_create(
			user=patient,
			defaults={'patient_id': 'P-MR-EMAIL-001'},
		)
		record = MedicalRecord.objects.create(
			patient=patient,
			doctor=self.doctor,
			appointment=None,
			diagnosis='UTI',
			treatment='Rest',
		)
		factory = RequestFactory()
		request = factory.get('/')
		ok = email_patient_medical_record_results_ready(request, record)
		self.assertTrue(ok)
		self.assertEqual(len(mail.outbox), 1)
		self.assertEqual(mail.outbox[0].to, ['mr-results-patient@example.com'])
		self.assertIn(f'/medical-records/{record.pk}/', mail.outbox[0].body)
		self.assertNotIn('/guest/medical-record/', mail.outbox[0].body)
		self.assertIn('sign in', mail.outbox[0].body.lower())

	def test_email_medical_record_results_ready_routes_guest_and_patient(self):
		from core.guest_emails import email_medical_record_results_ready
		from core.models import PatientProfile
		from medical_records.models import MedicalRecord

		guest_record = MedicalRecord.objects.create(
			patient=self.guest,
			doctor=self.doctor,
			diagnosis='Guest case',
			treatment='Observe',
		)
		patient = User.objects.create_user(
			email='mr-route-patient@example.com',
			password='Pass123!',
			role='patient',
			is_active=True,
			first_name='Route',
			last_name='Patient',
		)
		PatientProfile.objects.update_or_create(
			user=patient,
			defaults={'patient_id': 'P-MR-ROUTE-001'},
		)
		patient_record = MedicalRecord.objects.create(
			patient=patient,
			doctor=self.doctor,
			diagnosis='Patient case',
			treatment='Observe',
		)
		factory = RequestFactory()
		request = factory.get('/')

		self.assertTrue(
			email_medical_record_results_ready(
				request, guest_record, created_by=self.doctor
			)
		)
		self.assertIn('/guest/medical-record/', mail.outbox[-1].body)

		self.assertTrue(email_medical_record_results_ready(request, patient_record))
		self.assertIn(f'/medical-records/{patient_record.pk}/', mail.outbox[-1].body)

	def test_email_guest_dental_record_results_ready(self):
		from core.guest_emails import email_guest_dental_record_results_ready
		from dental_records.models import DentalRecord

		record = DentalRecord.objects.create(
			patient=self.guest,
			examined_by=self.doctor,
			status='completed',
			designation='student',
			department_college_office='Guest',
			email='guest-patient@example.com',
			gender='female',
			civil_status='single',
			address='123 St',
			date_of_birth=date(1995, 1, 1),
			place_of_birth='Davao',
			contact_number='+639171234567',
			guardian_name='Parent',
			guardian_contact='+639179876543',
			date_of_examination=date.today(),
			consent_signed=True,
			informed_consent_signed=True,
		)
		factory = RequestFactory()
		request = factory.get('/')
		ok = email_guest_dental_record_results_ready(
			request, record, created_by=self.doctor
		)
		self.assertTrue(ok)
		self.assertEqual(len(mail.outbox), 1)
		self.assertEqual(mail.outbox[0].to, ['guest-patient@example.com'])
		self.assertIn('/guest/dental-record/', mail.outbox[0].body)
		self.assertNotIn('/dental-records/', mail.outbox[0].body)

		_, raw = issue_guest_access_token(
			self.guest,
			GuestAccessToken.Purpose.DENTAL_RECORD,
			record.pk,
			created_by=self.doctor,
		)
		response = self.client.get(
			reverse('core:guest_dental_record', kwargs={'token': raw})
		)
		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Your dental record')
		self.assertContains(response, 'View-only')

	def test_email_appointment_results_ready_routes_guest_to_dental_link(self):
		from core.guest_emails import email_appointment_results_ready
		from dental_records.models import DentalRecord

		appointment = Appointment.objects.create(
			patient=self.guest,
			doctor=self.doctor,
			appointment_type='dental',
			date=date.today() - timedelta(days=1),
			time=time(10, 0),
			reason='Cleaning',
			status='completed',
		)
		DentalRecord.objects.create(
			patient=self.guest,
			examined_by=self.doctor,
			appointment=appointment,
			status='completed',
			designation='student',
			department_college_office='Guest',
			email='guest-patient@example.com',
			gender='female',
			civil_status='single',
			address='123 St',
			date_of_birth=date(1995, 1, 1),
			place_of_birth='Davao',
			contact_number='+639171234567',
			guardian_name='Parent',
			guardian_contact='+639179876543',
			date_of_examination=date.today(),
			consent_signed=True,
			informed_consent_signed=True,
		)
		factory = RequestFactory()
		request = factory.get('/')
		ok = email_appointment_results_ready(request, appointment, created_by=self.doctor)
		self.assertTrue(ok)
		self.assertEqual(len(mail.outbox), 1)
		self.assertIn('/guest/dental-record/', mail.outbox[0].body)

	def test_email_appointment_results_ready_routes_guest_to_medical_link(self):
		from core.guest_emails import email_appointment_results_ready
		from medical_records.models import MedicalRecord

		appointment = Appointment.objects.create(
			patient=self.guest,
			doctor=self.doctor,
			appointment_type='consultation',
			date=date.today() - timedelta(days=1),
			time=time(11, 0),
			reason='Follow-up',
			status='completed',
		)
		MedicalRecord.objects.create(
			patient=self.guest,
			doctor=self.doctor,
			appointment=appointment,
			diagnosis='Resolved',
			treatment='None',
		)
		factory = RequestFactory()
		request = factory.get('/')
		ok = email_appointment_results_ready(request, appointment, created_by=self.doctor)
		self.assertTrue(ok)
		self.assertEqual(len(mail.outbox), 1)
		self.assertIn('/guest/medical-record/', mail.outbox[0].body)

	def test_email_guest_health_form_pending(self):
		health_form = HealthProfileForm.objects.create(
			user=self.guest,
			status=HealthProfileForm.Status.INCOMPLETE,
			first_name='Guest',
			last_name='Patient',
			email_address='guest-patient@example.com',
		)
		factory = RequestFactory()
		request = factory.get('/')
		ok = email_guest_health_form_pending(request, health_form, created_by=self.doctor)
		self.assertTrue(ok)
		self.assertEqual(len(mail.outbox), 1)
		self.assertIn('/guest/health-form/', mail.outbox[0].body)
		self.assertIn('cancel', mail.outbox[0].alternatives[0][0].lower())

	def test_email_patient_health_form_pending(self):
		from core.guest_emails import email_patient_health_form_pending
		from core.models import PatientProfile

		patient = User.objects.create_user(
			email='hf-patient@example.com',
			password='Pass123!',
			role='patient',
			is_active=True,
			first_name='HF',
			last_name='Patient',
		)
		PatientProfile.objects.update_or_create(
			user=patient,
			defaults={'patient_id': 'P-HF-EMAIL-001'},
		)
		health_form = HealthProfileForm.objects.create(
			user=patient,
			status=HealthProfileForm.Status.INCOMPLETE,
			first_name='HF',
			last_name='Patient',
			email_address=patient.email,
		)
		factory = RequestFactory()
		request = factory.get('/')
		ok = email_patient_health_form_pending(request, health_form)
		self.assertTrue(ok)
		self.assertEqual(len(mail.outbox), 1)
		self.assertEqual(mail.outbox[0].to, [patient.email])
		self.assertIn(f'/health-forms/{health_form.pk}/edit/', mail.outbox[0].body)
		self.assertNotIn('/guest/health-form/', mail.outbox[0].body)
		self.assertIn('sign in', mail.outbox[0].body.lower())

	def test_health_form_email_fails_clearly_when_clinic_email_disabled(self):
		from core.guest_emails import email_guest_health_form_pending
		from core.settings_service import invalidate_settings_cache

		ClinicSettings.objects.filter(pk=ClinicSettings.SINGLETON_PK).update(
			enable_email_notifications=False,
		)
		invalidate_settings_cache()
		health_form = HealthProfileForm.objects.create(
			user=self.guest,
			status=HealthProfileForm.Status.INCOMPLETE,
			first_name='Guest',
			last_name='Patient',
			email_address='guest-patient@example.com',
		)
		factory = RequestFactory()
		request = factory.get('/')
		with self.assertRaisesMessage(RuntimeError, 'Clinic email notifications are turned off'):
			email_guest_health_form_pending(request, health_form, created_by=self.doctor)


class GuestSubmitValidationTests(TestCase):
	def test_guest_submit_skips_institutional_fields(self):
		from health_forms_services.services import validate_submit_for_review

		guest = create_guest_user(contact_email='validate-guest@example.com')
		health_form = HealthProfileForm(
			user=guest,
			first_name='Guest',
			last_name='Patient',
			date_of_birth=date(2000, 1, 1),
			gender='female',
			designation='guest',
			mobile_number='+639171234567',
			email_address='validate-guest@example.com',
			department_college_office='',
		)
		self.assertEqual(validate_submit_for_review(health_form), [])

	def test_non_guest_still_requires_department(self):
		from health_forms_services.services import validate_submit_for_review

		patient = User.objects.create_user(
			email='validate-patient@example.com',
			password='Pass123!',
			role='patient',
			is_active=True,
		)
		health_form = HealthProfileForm(
			user=patient,
			first_name='Pat',
			last_name='Ient',
			date_of_birth=date(2000, 1, 1),
			gender='female',
			designation='student',
			mobile_number='+639171234567',
			email_address='validate-patient@example.com',
			department_college_office='',
		)
		errors = validate_submit_for_review(health_form)
		self.assertTrue(any('Department' in err for err in errors))


@override_settings(
	EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
	MIDDLEWARE=_TEST_MIDDLEWARE,
)
class GuestDentalIntakeTests(TestCase):
	def setUp(self):
		_enable_clinic_email()
		self.doctor = User.objects.create_user(
			email='doc-dental-intake@test.com',
			password='DoctorPass123!',
			role='doctor',
			is_staff=True,
			is_active=True,
			first_name='Doc',
			last_name='Dental',
		)
		_complete_staff_like_profile(self.doctor, 'DOC-DENTAL-INTAKE')
		self.guest = create_guest_user(
			first_name='Guest',
			last_name='Dental',
			contact_email='guest-dental@example.com',
		)
		self.client = Client()

	def _make_awaiting_record(self):
		from dental_records.models import DentalRecord

		return DentalRecord.objects.create(
			patient=self.guest,
			examined_by=self.doctor,
			status='pending',
			intake_status='awaiting_guest',
			designation='student',
			department_college_office='Guest',
			email='guest-dental@example.com',
			date_of_examination=date.today(),
		)

	def test_email_guest_dental_intake_pending(self):
		from core.guest_emails import email_guest_dental_intake_pending

		record = self._make_awaiting_record()
		factory = RequestFactory()
		request = factory.get('/')
		ok = email_guest_dental_intake_pending(request, record, created_by=self.doctor)
		self.assertTrue(ok)
		self.assertEqual(len(mail.outbox), 1)
		self.assertIn('/guest/dental-intake/', mail.outbox[0].body)
		self.assertTrue(
			GuestAccessToken.objects.filter(
				user=self.guest,
				purpose=GuestAccessToken.Purpose.DENTAL_INTAKE,
				object_id=record.pk,
				revoked_at__isnull=True,
			).exists()
		)

	def test_guest_dental_intake_save_and_submit(self):
		from core.models import Notification
		from dental_records.models import DentalRecord

		record = self._make_awaiting_record()
		_, raw = issue_guest_access_token(
			self.guest,
			GuestAccessToken.Purpose.DENTAL_INTAKE,
			record.pk,
			created_by=self.doctor,
		)
		url = reverse('core:guest_dental_intake', kwargs={'token': raw})

		save_resp = self.client.post(
			url,
			{
				'action': 'save',
				'middle_name': 'M',
				'gender': 'female',
				'civil_status': 'single',
				'address': '123 Guest St',
				'date_of_birth': '1995-05-05',
				'place_of_birth': 'Davao',
				'email': 'guest-dental@example.com',
				'contact_number': '9171234567',
				'guardian_name': 'Parent',
				'guardian_contact': '9179876543',
			},
		)
		self.assertEqual(save_resp.status_code, 302)
		record.refresh_from_db()
		self.assertEqual(record.intake_status, 'awaiting_guest')
		self.assertEqual(record.address, '123 Guest St')
		self.assertEqual(record.department_college_office, 'Guest')

		submit_resp = self.client.post(
			url,
			{
				'action': 'submit',
				'middle_name': 'M',
				'gender': 'female',
				'civil_status': 'single',
				'address': '123 Guest St',
				'date_of_birth': '1995-05-05',
				'place_of_birth': 'Davao',
				'email': 'guest-dental@example.com',
				'contact_number': '9171234567',
				'guardian_name': 'Parent',
				'guardian_contact': '9179876543',
				'consent_signed': 'on',
				'consent_date': date.today().isoformat(),
				'informed_consent_signed': 'on',
				'informed_consent_date': date.today().isoformat(),
			},
		)
		self.assertEqual(submit_resp.status_code, 200)
		self.assertContains(submit_resp, 'Intake submitted')
		record.refresh_from_db()
		self.assertEqual(record.intake_status, 'guest_submitted')
		self.assertTrue(record.consent_signed)
		self.assertEqual(record.status, 'pending')
		self.assertTrue(
			Notification.objects.filter(
				user=self.doctor,
				title='Guest dental intake submitted',
			).exists()
		)

		closed = self.client.get(url)
		self.assertEqual(closed.status_code, 200)
		self.assertContains(closed, 'Intake closed')
