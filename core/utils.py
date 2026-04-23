import re

from django.db.models import Count, Q, Avg
from django.utils import timezone
from django.core.paginator import Paginator
from django.core.exceptions import ValidationError
from datetime import datetime, timedelta
from django.contrib.auth import get_user_model
from .profile_policy import (
    STUDENT_PROFILE_REQUIRED_FIELDS,
    STAFF_PROFILE_REQUIRED_FIELDS,
    DOCTOR_PROFILE_REQUIRED_FIELDS,
)

User = get_user_model()


# ---------------------------------------------------------------------------
# Philippine Mobile Number Validation & Normalization
# ---------------------------------------------------------------------------

def clean_philippine_phone(value):
    """Validate and normalize a Philippine mobile number to E.164 format.

    Accepted inputs (spaces, dashes, dots, parentheses are ignored):
        +639171234567   →  +639171234567
        09171234567     →  +639171234567
        9171234567      →  +639171234567
        +63 917 123 4567  (formatted)

    Returns:
        str  –  Normalized number in +63XXXXXXXXXX format.

    Raises:
        ValidationError  –  If *value* is not a valid PH mobile number.
    """
    if not value:
        return value

    raw = value.strip()

    # Preserve a leading '+' then keep only digits
    has_plus = raw.startswith('+')
    digits = re.sub(r'\D', '', raw)

    # Extract the 10-digit mobile part (must start with 9)
    mobile = None

    if has_plus and digits.startswith('63') and len(digits) == 12:
        mobile = digits[2:]                       # +639XXXXXXXXX
    elif digits.startswith('63') and len(digits) == 12:
        mobile = digits[2:]                       # 639XXXXXXXXX (no +)
    elif digits.startswith('0') and len(digits) == 11:
        mobile = digits[1:]                       # 09XXXXXXXXX
    elif len(digits) == 10:
        mobile = digits                           # 9XXXXXXXXX

    if mobile and len(mobile) == 10 and mobile[0] == '9':
        return f'+63{mobile}'

    raise ValidationError(
        'Enter a valid Philippine mobile number '
        '(e.g., 09171234567 or +639171234567).'
    )


def get_user_profile(user):
    """Get user profile based on role"""
    from .models import StudentProfile, StaffProfile
    
    if user.role == 'student':
        try:
            return user.student_profile
        except StudentProfile.DoesNotExist:
            return None
    elif user.role in ['staff', 'doctor']:
        try:
            return user.staff_profile
        except StaffProfile.DoesNotExist:
            return None
    return None


def is_profile_complete(user):
    """Check if user's profile is complete with all required fields"""
    try:
        profile = get_user_profile(user)
        
        if not profile:
            return False

        if user.role == 'student':
            return is_student_profile_complete(profile)
        elif user.role == 'staff':
            return is_staff_profile_complete(profile)
        elif user.role == 'doctor':
            return is_doctor_profile_complete(profile)
        
        return True
    except Exception:
        return False


def is_student_profile_complete(profile):
    """Check if student profile is complete with all required fields"""
    for field in STUDENT_PROFILE_REQUIRED_FIELDS:
        value = getattr(profile, field, None)
        if not value or (isinstance(value, str) and not value.strip()):
            return False
    
    return True


def is_staff_profile_complete(profile):
    """Check if staff profile is complete with all required fields"""
    for field in STAFF_PROFILE_REQUIRED_FIELDS:
        value = getattr(profile, field, None)
        if not value or (isinstance(value, str) and not value.strip()):
            return False
    
    return True


def is_doctor_profile_complete(profile):
    """Check if doctor profile is complete with all required fields"""
    for field in DOCTOR_PROFILE_REQUIRED_FIELDS:
        value = getattr(profile, field, None)
        if not value or (isinstance(value, str) and not value.strip()):
            return False

    return True


# Human-readable labels for profile fields shown on the "profile required" page
FIELD_LABELS = {
    'student_id':        'Student ID',
    'middle_name':       'Middle Name',
    'gender':            'Gender',
    'civil_status':      'Civil Status',
    'date_of_birth':     'Date of Birth',
    'place_of_birth':    'Place of Birth',
    'age':               'Age',
    'address':           'Address',
    'phone':             'Phone Number',
    'telephone_number':  'Telephone Number',
    'emergency_contact': 'Emergency Contact Name',
    'emergency_phone':   'Emergency Contact Number',
    'department':        'Department',
    'blood_type':        'Blood Type',
    'staff_id':          'Staff ID',
    'license_number':    'License Number',
    'ptr_no':            'PTR No. (Professional Tax Receipt)',
    'position':          'Position / Title',
}

# Required fields per role
STUDENT_REQUIRED = STUDENT_PROFILE_REQUIRED_FIELDS
STAFF_REQUIRED = STAFF_PROFILE_REQUIRED_FIELDS
DOCTOR_REQUIRED = DOCTOR_PROFILE_REQUIRED_FIELDS


def get_missing_profile_fields(user):
    """Return a list of (field_name, friendly_label) tuples for missing required fields."""
    profile = get_user_profile(user)

    if user.role == 'student':
        required_fields = STUDENT_REQUIRED
    elif user.role == 'staff':
        required_fields = STAFF_REQUIRED
    elif user.role == 'doctor':
        required_fields = DOCTOR_REQUIRED
    else:
        return []

    if not profile:
        # Profile doesn't exist yet — all required fields are missing
        return [(f, FIELD_LABELS.get(f, f.replace('_', ' ').title())) for f in required_fields]

    missing = []
    for field in required_fields:
        value = getattr(profile, field, None)
        if not value or (isinstance(value, str) and not value.strip()):
            missing.append((field, FIELD_LABELS.get(field, field.replace('_', ' ').title())))
    return missing


def check_permission(user, obj, field='user'):
    """Check if user has permission to access object"""
    if user.role == 'admin':
        return True
    
    if hasattr(obj, field):
        return getattr(obj, field) == user
    
    # For appointments, check both student and doctor
    if hasattr(obj, 'student') and hasattr(obj, 'doctor'):
        return obj.student == user or obj.doctor == user
    
    return False


def paginate_queryset(queryset, request, per_page=10):
    """Paginate queryset"""
    paginator = Paginator(queryset, per_page)
    page = request.GET.get('page')
    return paginator.get_page(page)


def parse_date(date_string):
    """Parse date string safely"""
    if not date_string:
        return None
    try:
        return datetime.strptime(date_string, '%Y-%m-%d').date()
    except ValueError:
        return None


def get_queryset_by_role(model, user, student_field='student', doctor_field='doctor'):
    """Get queryset based on user role for models with student/doctor fields"""
    if user.role == 'student':
        return model.objects.filter(**{student_field: user})
    elif user.role == 'staff':
        if hasattr(model.objects.first(), doctor_field):
            return model.objects.filter(**{doctor_field: user})
        else:
            return model.objects.all()  # For models without doctor field
    elif user.role == 'admin':
        return model.objects.all()
    else:
        return model.objects.none()


def apply_date_filters(queryset, request, date_field='created_at'):
    """Apply date filters to queryset"""
    date_from = parse_date(request.GET.get('date_from'))
    date_to = parse_date(request.GET.get('date_to'))
    
    if date_from:
        if '__date' in date_field:
            queryset = queryset.filter(**{f'{date_field}__gte': date_from})
        else:
            queryset = queryset.filter(**{f'{date_field}__date__gte': date_from})
    
    if date_to:
        if '__date' in date_field:
            queryset = queryset.filter(**{f'{date_field}__lte': date_to})
        else:
            queryset = queryset.filter(**{f'{date_field}__date__lte': date_to})
    
    return queryset


def create_notification(user, title, message, notification_type='general', related_id=None, transaction_type=None):
    """
    Helper function to create notifications
    """
    from .models import Notification
    
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
    from .models import Notification
    
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
    staff = User.objects.filter(role__in=['staff', 'doctor'])
    return create_bulk_notifications(staff, title, message, notification_type, related_id, transaction_type)


def notify_all_users(title, message, notification_type='general', related_id=None, transaction_type=None):
    """
    Send notification to all users
    """
    users = User.objects.filter(role__in=['student', 'staff'])
    return create_bulk_notifications(users, title, message, notification_type, related_id, transaction_type)


def get_dashboard_stats(user):
    """Get dashboard statistics based on user role"""
    from appointments.models import Appointment
    from medical_records.models import MedicalRecord
    from document_request.models import DocumentRequest as CertificateRequest
    from health_tips.models import HealthTip
    from feedback.models import Feedback
    
    stats = {}
    
    if user.role == 'student':
        stats = {
            'upcoming_appointments': Appointment.objects.filter(
                student=user, 
                date__gte=timezone.now().date(),
                status__in=['pending']
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
            'total_staff': User.objects.filter(role__in=['staff', 'doctor']).count(),
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
    from appointments.models import Appointment
    from medical_records.models import MedicalRecord
    from document_request.models import DocumentRequest as CertificateRequest
    from feedback.models import Feedback
    
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
    from appointments.models import Appointment
    from document_request.models import DocumentRequest as CertificateRequest
    
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
