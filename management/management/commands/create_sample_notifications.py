from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from management.models import Notification, CertificateRequest
from appointments.models import Appointment
from management.utils import notify_all_students, notify_all_staff, create_notification
import random
from datetime import datetime, timedelta

User = get_user_model()

class Command(BaseCommand):
    help = 'Create sample notifications for testing'

    def add_arguments(self, parser):
        parser.add_argument(
            '--count',
            type=int,
            default=10,
            help='Number of sample notifications to create per user'
        )

    def handle(self, *args, **options):
        count = options['count']
        
        # Get some existing appointments and certificate requests for linking
        appointments = list(Appointment.objects.all()[:10])
        cert_requests = list(CertificateRequest.objects.all()[:10])
        
        # Sample notification data with specific transaction types
        sample_notifications = [
            {
                'title': 'Appointment Reminder',
                'message': 'You have an upcoming appointment tomorrow at 10:00 AM with Dr. Johnson.',
                'type': 'appointment',
                'transaction_type': 'appointment_reminder',
                'get_related_id': lambda user: random.choice([a.id for a in appointments if a.student == user] + [None]) if appointments else None
            },
            {
                'title': 'Health Tip: Stay Hydrated',
                'message': 'Remember to drink at least 8 glasses of water daily for optimal health.',
                'type': 'health_tip',
                'transaction_type': 'health_tip_new',
                'get_related_id': lambda user: None
            },
            {
                'title': 'Certificate Ready',
                'message': 'Your medical fitness certificate is ready for collection.',
                'type': 'certificate',
                'transaction_type': 'certificate_ready',
                'get_related_id': lambda user: random.choice([c.id for c in cert_requests if c.student == user] + [None]) if cert_requests else None
            },
            {
                'title': 'New Health Article',
                'message': 'Check out our latest article on stress management techniques.',
                'type': 'health_tip',
                'transaction_type': 'health_tip_updated',
                'get_related_id': lambda user: None
            },
            {
                'title': 'Appointment Confirmed',
                'message': 'Your appointment for December 15th has been confirmed.',
                'type': 'appointment',
                'transaction_type': 'appointment_confirmed',
                'get_related_id': lambda user: random.choice([a.id for a in appointments if a.student == user] + [None]) if appointments else None
            },
            {
                'title': 'Vaccination Reminder',
                'message': 'Annual flu vaccination is now available. Schedule your appointment today.',
                'type': 'general',
                'transaction_type': 'general_announcement',
                'get_related_id': lambda user: None
            },
            {
                'title': 'Certificate Request Approved',
                'message': 'Your certificate request has been approved and is being processed.',
                'type': 'certificate',
                'transaction_type': 'certificate_approved',
                'get_related_id': lambda user: random.choice([c.id for c in cert_requests if c.student == user] + [None]) if cert_requests else None
            },
            {
                'title': 'Health Check Reminder',
                'message': 'It\'s time for your annual health checkup. Book an appointment today.',
                'type': 'appointment',
                'transaction_type': 'appointment_scheduled',
                'get_related_id': lambda user: random.choice([a.id for a in appointments if a.student == user] + [None]) if appointments else None
            },
            {
                'title': 'Medical Record Updated',
                'message': 'Your medical record has been updated with new information.',
                'type': 'general',
                'transaction_type': 'medical_record_updated',
                'get_related_id': lambda user: None
            },
            {
                'title': 'Certificate Request Submitted',
                'message': 'Your certificate request has been received and is under review.',
                'type': 'certificate',
                'transaction_type': 'certificate_requested',
                'get_related_id': lambda user: random.choice([c.id for c in cert_requests if c.student == user] + [None]) if cert_requests else None
            }
        ]
        
        users = User.objects.filter(role__in=['student', 'staff'])
        total_created = 0
        
        for user in users:
            user_notifications = random.sample(sample_notifications, min(count, len(sample_notifications)))
            
            for i, notif_data in enumerate(user_notifications):
                # Create some notifications as read and some as unread
                is_read = random.choice([True, False])
                
                # Get related_id if applicable
                related_id = notif_data['get_related_id'](user) if notif_data['get_related_id'] else None
                
                # Create notification with slightly different timestamps
                created_at = datetime.now() - timedelta(
                    hours=random.randint(1, 72),
                    minutes=random.randint(0, 59)
                )
                
                notification = Notification.objects.create(
                    user=user,
                    title=notif_data['title'],
                    message=notif_data['message'],
                    notification_type=notif_data['type'],
                    transaction_type=notif_data.get('transaction_type'),
                    related_id=related_id,
                    is_read=is_read
                )
                
                # Update the created_at timestamp
                notification.created_at = created_at
                notification.save(update_fields=['created_at'])
                
                total_created += 1
        
        # Create some system-wide announcements
        system_announcements = [
            {
                'title': 'System Maintenance Notice',
                'message': 'The clinic management system will undergo maintenance this weekend from 10 PM to 6 AM.',
                'type': 'general',
                'transaction_type': 'system_maintenance'
            },
            {
                'title': 'New Health Services Available',
                'message': 'We\'re excited to announce new mental health counseling services are now available.',
                'type': 'general',
                'transaction_type': 'general_announcement'
            }
        ]
        
        for announcement in system_announcements:
            # Send to all users
            all_users = User.objects.filter(role__in=['student', 'staff'])
            for user in all_users:
                create_notification(
                    user,
                    announcement['title'],
                    announcement['message'],
                    announcement['type'],
                    transaction_type=announcement['transaction_type']
                )
                total_created += 1
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully created {total_created} sample notifications')
        )
