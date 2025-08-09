from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from management.models import Notification
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
        
        # Sample notification data
        sample_notifications = [
            {
                'title': 'Appointment Reminder',
                'message': 'You have an upcoming appointment tomorrow at 10:00 AM with Dr. Johnson.',
                'type': 'appointment'
            },
            {
                'title': 'Health Tip: Stay Hydrated',
                'message': 'Remember to drink at least 8 glasses of water daily for optimal health.',
                'type': 'health_tip'
            },
            {
                'title': 'Certificate Ready',
                'message': 'Your medical fitness certificate is ready for collection.',
                'type': 'certificate'
            },
            {
                'title': 'New Health Article',
                'message': 'Check out our latest article on stress management techniques.',
                'type': 'health_tip'
            },
            {
                'title': 'Appointment Confirmed',
                'message': 'Your appointment for December 15th has been confirmed.',
                'type': 'appointment'
            },
            {
                'title': 'Vaccination Reminder',
                'message': 'Annual flu vaccination is now available. Schedule your appointment today.',
                'type': 'general'
            },
            {
                'title': 'Certificate Request Update',
                'message': 'Your certificate request has been approved and is being processed.',
                'type': 'certificate'
            },
            {
                'title': 'Health Check Reminder',
                'message': 'It\'s time for your annual health checkup. Book an appointment today.',
                'type': 'appointment'
            },
        ]
        
        users = User.objects.filter(role__in=['student', 'staff'])
        total_created = 0
        
        for user in users:
            user_notifications = random.sample(sample_notifications, min(count, len(sample_notifications)))
            
            for i, notif_data in enumerate(user_notifications):
                # Create some notifications as read and some as unread
                is_read = random.choice([True, False])
                
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
                'type': 'general'
            },
            {
                'title': 'New Health Services Available',
                'message': 'We\'re excited to announce new mental health counseling services are now available.',
                'type': 'general'
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
                    announcement['type']
                )
                total_created += 1
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully created {total_created} sample notifications')
        )
