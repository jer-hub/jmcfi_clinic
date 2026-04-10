from datetime import date

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from core.models import Notification, StaffProfile, StudentProfile

from .models import Conversation, ConversationParticipant
from .services import (
    create_announcement_conversation,
    get_or_create_direct_conversation,
    get_unread_message_count,
    send_conversation_message,
)


User = get_user_model()


class MessagingTestCase(TestCase):
    def setUp(self):
        self.student = User.objects.create_user(
            email='student@example.com',
            password='password123',
            first_name='Stu',
            last_name='Dent',
            role='student',
        )
        StudentProfile.objects.filter(user=self.student).update(
            student_id='S-1001',
            date_of_birth=date(2001, 1, 1),
            phone='+639171111111',
            emergency_contact='Parent One',
            emergency_phone='+639171111112',
            blood_type='O+',
        )

        self.doctor = User.objects.create_user(
            email='doctor@example.com',
            password='password123',
            first_name='Doc',
            last_name='Tor',
            role='doctor',
        )
        StaffProfile.objects.filter(user=self.doctor).update(
            staff_id='D-1001',
            department='Clinic',
            phone='+639171111113',
            license_number='LIC-1001',
            ptr_no='PTR-1001',
        )

        self.staff = User.objects.create_user(
            email='staff@example.com',
            password='password123',
            first_name='Staff',
            last_name='Member',
            role='staff',
        )
        StaffProfile.objects.filter(user=self.staff).update(
            staff_id='T-1001',
            department='Clinic',
            phone='+639171111114',
            license_number='LIC-1002',
            ptr_no='PTR-1002',
        )

        self.admin = User.objects.create_user(
            email='admin@example.com',
            password='password123',
            first_name='Ad',
            last_name='Min',
            role='admin',
        )

        self.outsider = User.objects.create_user(
            email='outsider@example.com',
            password='password123',
            first_name='Out',
            last_name='Sider',
            role='student',
        )
        StudentProfile.objects.filter(user=self.outsider).update(
            student_id='S-1002',
            date_of_birth=date(2002, 2, 2),
            phone='+639171111115',
            emergency_contact='Parent Two',
            emergency_phone='+639171111116',
            blood_type='A+',
        )


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
    def _force_login_complete(self, client, user):
        client.force_login(user)
        session = client.session
        session[f'profile_complete_{user.id}'] = True
        session.save()

    def test_non_participant_cannot_access_conversation(self):
        conversation, _ = get_or_create_direct_conversation(self.student, self.doctor)
        send_conversation_message(conversation, self.student, 'Private note')

        client = Client()
        self._force_login_complete(client, self.outsider)
        response = client.get(reverse('messaging:conversation_detail', args=[conversation.id]))

        self.assertEqual(response.status_code, 404)

    def test_student_can_start_conversation(self):
        client = Client()
        self._force_login_complete(client, self.student)

        response = client.post(reverse('messaging:start_conversation'), {
            'recipient': self.doctor.id,
            'body': 'Need a follow-up consultation.',
        })

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Conversation.objects.count(), 1)

    def test_staff_can_create_announcement(self):
        client = Client()
        self._force_login_complete(client, self.staff)

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

        response = client.get(reverse('messaging:start_conversation'))

        self.assertEqual(response.status_code, 403)