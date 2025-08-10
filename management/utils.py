from django.db.models import Count, Q, Avg
from django.utils import timezone
from datetime import datetime, timedelta
from .models import Appointment, MedicalRecord, CertificateRequest, HealthTip, Feedback, Notification
from django.contrib.auth import get_user_model

User = get_user_model()

def create_notification(user, title, message, notification_type='general', related_id=None, transaction_type=None):
    """
    Helper function to create notifications
    """
    return Notification.objects.create(
        user=user,
        title=title,
        message=message,
        notification_type=notification_type,
        related_id=related_id,
        transaction_type=transaction_type
    )

def create_bulk_notifications(users, title, message, notification_type='general', related_id=None, transaction_type=None):
    """
    Create notifications for multiple users
    """
    notifications = [
        Notification(
            user=user,
            title=title,
            message=message,
            notification_type=notification_type,
            related_id=related_id,
            transaction_type=transaction_type
        )
        for user in users
    ]
    return Notification.objects.bulk_create(notifications)

def notify_all_students(title, message, notification_type='general', related_id=None, transaction_type=None):
    """
    Send notification to all students
    """
    students = User.objects.filter(role='student')
    return create_bulk_notifications(students, title, message, notification_type, related_id, transaction_type)

def notify_all_staff(title, message, notification_type='general', related_id=None, transaction_type=None):
    """
    Send notification to all staff
    """
    staff = User.objects.filter(role='staff')
    return create_bulk_notifications(staff, title, message, notification_type, related_id, transaction_type)

def notify_all_users(title, message, notification_type='general', related_id=None, transaction_type=None):
    """
    Send notification to all users
    """
    users = User.objects.filter(role__in=['student', 'staff'])
    return create_bulk_notifications(users, title, message, notification_type, related_id, transaction_type)

def get_dashboard_stats(user):
    """Get dashboard statistics based on user role"""
    stats = {}
    
    if user.role == 'student':
        stats = {
            'upcoming_appointments': Appointment.objects.filter(
                student=user, 
                date__gte=timezone.now().date(),
                status__in=['pending', 'confirmed']
            ).count(),
            'total_appointments': Appointment.objects.filter(student=user).count(),
            'medical_records': MedicalRecord.objects.filter(student=user).count(),
            'pending_certificates': CertificateRequest.objects.filter(
                student=user,
                status='pending'
            ).count(),
            'unread_notifications': user.notifications.filter(is_read=False).count(),
        }
    
    elif user.role == 'staff':
        today = timezone.now().date()
        stats = {
            'today_appointments': Appointment.objects.filter(
                doctor=user,
                date=today
            ).count(),
            'pending_appointments': Appointment.objects.filter(
                doctor=user,
                status='pending'
            ).count(),
            'total_patients': MedicalRecord.objects.filter(
                doctor=user
            ).values('student').distinct().count(),
            'pending_certificates': CertificateRequest.objects.filter(
                status='pending'
            ).count(),
            'completed_appointments': Appointment.objects.filter(
                doctor=user,
                status='completed'
            ).count(),
        }
    
    elif user.role == 'admin':
        today = timezone.now().date()
        stats = {
            'total_students': User.objects.filter(role='student').count(),
            'total_staff': User.objects.filter(role='staff').count(),
            'today_appointments': Appointment.objects.filter(date=today).count(),
            'pending_certificates': CertificateRequest.objects.filter(
                status='pending'
            ).count(),
            'total_appointments': Appointment.objects.count(),
            'total_records': MedicalRecord.objects.count(),
            'total_certificates': CertificateRequest.objects.count(),
            'total_health_tips': HealthTip.objects.filter(is_active=True).count(),
            'avg_rating': Feedback.objects.aggregate(
                avg_rating=Avg('rating')
            )['avg_rating'] or 0,
        }
    
    return stats

def get_recent_activity(user, limit=5):
    """Get recent activity based on user role"""
    activity = {}
    
    if user.role == 'student':
        activity = {
            'appointments': Appointment.objects.filter(
                student=user
            ).order_by('-created_at')[:limit],
            'records': MedicalRecord.objects.filter(
                student=user
            ).order_by('-created_at')[:limit],
            'certificates': CertificateRequest.objects.filter(
                student=user
            ).order_by('-created_at')[:limit],
        }
    
    elif user.role == 'staff':
        today = timezone.now().date()
        activity = {
            'today_appointments': Appointment.objects.filter(
                doctor=user,
                date=today
            ).order_by('time')[:limit],
            'recent_records': MedicalRecord.objects.filter(
                doctor=user
            ).order_by('-created_at')[:limit],
            'pending_certificates': CertificateRequest.objects.filter(
                status='pending'
            ).order_by('-created_at')[:limit],
        }
    
    elif user.role == 'admin':
        today = timezone.now().date()
        activity = {
            'recent_appointments': Appointment.objects.filter(
                date=today
            ).order_by('-created_at')[:limit],
            'recent_feedbacks': Feedback.objects.all().order_by('-created_at')[:limit],
            'recent_certificates': CertificateRequest.objects.all().order_by('-created_at')[:limit],
        }
    
    return activity

def get_weekly_stats():
    """Get weekly statistics for charts"""
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=7)
    
    appointments_by_day = []
    for i in range(7):
        date = start_date + timedelta(days=i)
        count = Appointment.objects.filter(date=date).count()
        appointments_by_day.append({
            'date': date.strftime('%Y-%m-%d'),
            'count': count
        })
    
    return {
        'appointments_by_day': appointments_by_day,
        'appointment_types': Appointment.objects.values('appointment_type').annotate(
            count=Count('id')
        ).order_by('-count'),
        'certificate_status': CertificateRequest.objects.values('status').annotate(
            count=Count('id')
        ).order_by('-count'),
    }
