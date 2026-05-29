from datetime import date



from django.contrib.auth import get_user_model

from django.test import Client, TestCase

from django.urls import reverse



from core.models import Notification, PatientProfile, StaffProfile



from .models import Conversation, ConversationParticipant

from .services import (

    create_announcement_conversation,

    get_or_create_direct_conversation,

    get_unread_message_count,

    send_conversation_message,

)





User = get_user_model()





def _complete_patient_profile(user, patient_id='S-1001'):

    user.first_name = user.first_name or 'Stu'

    user.last_name = user.last_name or 'Dent'

    user.save(update_fields=['first_name', 'last_name'])

    profile = user.patient_profile

    profile.patient_id = patient_id

    profile.middle_name = 'M'

    profile.gender = 'male'

    profile.civil_status = 'single'

    profile.date_of_birth = date(2001, 1, 1)

    profile.place_of_birth = 'City'

    profile.age = 24

    profile.address = '123 St'

    profile.phone = '+639171111111'

    profile.emergency_contact = 'Parent One'

    profile.emergency_phone = '+639171111112'

    profile.department = 'College'

    profile.course = 'BS Test'

    profile.year_level = '1st Year'

    profile.blood_type = 'O+'

    profile.save()

    user.__dict__.pop('patient_profile', None)

    user._state.fields_cache.pop('patient_profile', None)





def _complete_staff_like_profile(user, staff_id):

    user.first_name = user.first_name or 'Test'

    user.last_name = user.last_name or 'User'

    user.save(update_fields=['first_name', 'last_name'])

    profile, _ = StaffProfile.objects.get_or_create(user=user)

    profile.staff_id = staff_id

    profile.department = 'Clinic'

    profile.phone = '+639171111113'

    profile.license_number = 'LIC-1001'

    profile.ptr_no = 'PTR-1001'

    if user.role == 'doctor':

        profile.position = 'Physician'

    profile.save()

    user.__dict__.pop('staff_profile', None)

    user._state.fields_cache.pop('staff_profile', None)





class MessagingTestCase(TestCase):

    def setUp(self):

        self.student = User.objects.create_user(

            email='student@example.com',

            password='password123',

            first_name='Stu',

            last_name='Dent',

            role='patient',

        )

        _complete_patient_profile(self.student, 'S-1001')



        self.doctor = User.objects.create_user(

            email='doctor@example.com',

            password='password123',

            first_name='Doc',

            last_name='Tor',

            role='doctor',

        )

        _complete_staff_like_profile(self.doctor, 'D-1001')



        self.staff = User.objects.create_user(

            email='staff@example.com',

            password='password123',

            first_name='Staff',

            last_name='Member',

            role='staff',

        )

        _complete_staff_like_profile(self.staff, 'T-1001')



        self.admin = User.objects.create_user(

            email='admin@example.com',

            password='password123',

            first_name='Ad',

            last_name='Min',

            role='admin',

        )

        _complete_staff_like_profile(self.admin, 'A-1001')



        self.outsider = User.objects.create_user(

            email='outsider@example.com',

            password='password123',

            first_name='Out',

            last_name='Sider',

            role='patient',

        )

        _complete_patient_profile(self.outsider, 'S-1002')





class MessagingServiceTests(MessagingTestCase):

    def test_get_or_create_direct_conversation_reuses_existing_thread(self):

        first_conversation, created = get_or_create_direct_conversation(self.student, self.doctor)

        second_conversation, created_again = get_or_create_direct_conversation(self.student, self.doctor)



        self.assertTrue(created)

        self.assertFalse(created_again)

        self.assertEqual(first_conversation.id, second_conversation.id)

        self.assertEqual(ConversationParticipant.objects.filter(conversation=first_conversation).count(), 2)



    def test_send_message_creates_unread_state_without_notification_entry(self):

        conversation, _ = get_or_create_direct_conversation(self.student, self.doctor)



        send_conversation_message(conversation, self.student, 'Hello doctor')



        self.assertEqual(get_unread_message_count(self.doctor), 1)

        self.assertEqual(get_unread_message_count(self.student), 0)

        self.assertFalse(Notification.objects.filter(user=self.doctor, transaction_type='direct_message').exists())



    def test_announcement_is_read_only_for_recipients(self):

        conversation, _ = create_announcement_conversation(self.staff, 'Clinic advisory', 'The clinic closes early.', 'students')



        with self.assertRaises(PermissionError):

            send_conversation_message(conversation, self.student, 'Can I reply?')



    def test_student_to_student_direct_message_is_not_allowed(self):

        with self.assertRaises(PermissionError):

            get_or_create_direct_conversation(self.student, self.outsider)



    def test_staff_to_doctor_direct_message_is_not_allowed(self):

        with self.assertRaises(PermissionError):

            get_or_create_direct_conversation(self.staff, self.doctor)



    def test_student_to_staff_direct_message_is_allowed(self):

        conversation, created = get_or_create_direct_conversation(self.student, self.staff)

        self.assertTrue(created)

        self.assertEqual(conversation.participant_links.count(), 2)



    def test_doctor_to_student_direct_message_is_allowed(self):

        conversation, created = get_or_create_direct_conversation(self.doctor, self.student)

        self.assertTrue(created)

        self.assertEqual(conversation.participant_links.count(), 2)





class MessagingViewTests(MessagingTestCase):

    def test_non_participant_cannot_access_conversation(self):

        conversation, _ = get_or_create_direct_conversation(self.student, self.doctor)

        send_conversation_message(conversation, self.student, 'Private note')



        client = Client()

        client.force_login(self.outsider)

        response = client.get(reverse('messaging:conversation_detail', args=[conversation.id]))



        self.assertEqual(response.status_code, 404)



    def test_student_can_start_conversation(self):

        client = Client()

        client.force_login(self.student)



        response = client.post(reverse('messaging:start_conversation'), {

            'recipient': self.doctor.id,

            'body': 'Need a follow-up consultation.',

        })



        self.assertEqual(response.status_code, 302)

        self.assertEqual(Conversation.objects.count(), 1)



    def test_staff_can_create_announcement(self):

        client = Client()

        client.force_login(self.staff)



        response = client.post(reverse('messaging:create_announcement'), {

            'title': 'Stock update',

            'audience': 'students',

            'body': 'Bring your updated records when visiting the clinic.',

        })



        self.assertEqual(response.status_code, 302)

        conversation = Conversation.objects.get(conversation_type='announcement')

        self.assertEqual(conversation.participants.count(), 3)



    def test_admin_cannot_start_direct_conversation(self):

        client = Client()

        client.force_login(self.admin)



        response = client.get(reverse('messaging:start_conversation'), follow=True)



        self.assertEqual(response.status_code, 200)

        self.assertEqual(response.request['PATH_INFO'], reverse('messaging:inbox'))

        self.assertContains(response, 'Direct messaging is not available for your role.')


