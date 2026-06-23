from django.test import Client, TestCase, override_settings
from django.urls import reverse

from core.models import StaffProfile, User
from appointments.models import Appointment, AppointmentTypeDefault

TEST_MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
]


@override_settings(MIDDLEWARE=TEST_MIDDLEWARE)
class AppointmentTypeSettingsDoctorDropdownTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            email='appt-settings-admin@test.com',
            password='pw',
            role='admin',
            first_name='Admin',
            last_name='User',
        )
        self.doctor = User.objects.create_user(
            email='appt-settings-doctor@test.com',
            password='pw',
            role='doctor',
            first_name="Anne O'Brien",
            last_name='Smith',
        )
        StaffProfile.objects.update_or_create(
            user=self.doctor,
            defaults={'department': 'College of Nursing'},
        )
        self.client.force_login(self.admin)
        self._assign_all_doctors_to_defaults()

    def _assign_all_doctors_to_defaults(self):
        doctor_ids = [self.doctor.pk]
        for default in AppointmentTypeDefault.objects.all():
            default.assigned_doctors.set(doctor_ids)

    def test_settings_page_renders_all_doctors_available_when_all_selected(self):
        response = self.client.get(reverse('appointments:appointment_type_settings'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'All doctors available')
        self.assertContains(response, 'doctorDropdown(')
        self.assertContains(response, 'No doctors selected')
        self.assertContains(response, 'College of Nursing')
        self.assertContains(response, f'value="{self.doctor.pk}"')

    def test_settings_page_shows_no_doctors_selected_when_none_assigned(self):
        default = AppointmentTypeDefault.objects.get(
            appointment_type=Appointment.APPOINTMENT_TYPE_CHOICES[0][0],
        )
        default.assigned_doctors.clear()
        response = self.client.get(reverse('appointments:appointment_type_settings'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'No doctors selected')
        self.assertContains(response, 'None selected')

    def test_doctor_assignment_htmx_save_restricts_to_subset(self):
        other_doctor = User.objects.create_user(
            email='appt-settings-doctor-2@test.com',
            password='pw',
            role='doctor',
            first_name='Other',
            last_name='Doctor',
        )
        StaffProfile.objects.update_or_create(
            user=other_doctor,
            defaults={'department': 'College of Medicine'},
        )
        type_key = Appointment.APPOINTMENT_TYPE_CHOICES[0][0]
        default = AppointmentTypeDefault.objects.get(appointment_type=type_key)
        default.assigned_doctors.set([self.doctor, other_doctor])
        url = reverse('appointments:edit_appointment_type_default', kwargs={'type_key': type_key})
        response = self.client.post(
            url,
            {
                'appointment_type': type_key,
                'assigned_doctors': [str(self.doctor.pk)],
            },
            HTTP_HX_REQUEST='true',
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Restricted')
        default = AppointmentTypeDefault.objects.get(appointment_type=type_key)
        self.assertEqual(list(default.assigned_doctors.values_list('pk', flat=True)), [self.doctor.pk])

    def test_clear_doctor_assignment_htmx_save_blocks_booking(self):
        type_key = Appointment.APPOINTMENT_TYPE_CHOICES[0][0]
        default = AppointmentTypeDefault.objects.get(appointment_type=type_key)
        default.assigned_doctors.set([self.doctor])
        url = reverse('appointments:edit_appointment_type_default', kwargs={'type_key': type_key})
        response = self.client.post(
            url,
            {'appointment_type': type_key},
            HTTP_HX_REQUEST='true',
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'None selected')
        default.refresh_from_db()
        self.assertFalse(default.assigned_doctors.exists())

    def test_select_all_doctors_htmx_save_allows_open_booking(self):
        type_key = Appointment.APPOINTMENT_TYPE_CHOICES[0][0]
        default = AppointmentTypeDefault.objects.get(appointment_type=type_key)
        default.assigned_doctors.clear()
        url = reverse('appointments:edit_appointment_type_default', kwargs={'type_key': type_key})
        response = self.client.post(
            url,
            {
                'appointment_type': type_key,
                'assigned_doctors': [str(self.doctor.pk)],
            },
            HTTP_HX_REQUEST='true',
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'All available')
        default.refresh_from_db()
        self.assertEqual(list(default.assigned_doctors.values_list('pk', flat=True)), [self.doctor.pk])
