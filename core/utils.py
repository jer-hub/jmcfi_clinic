import re

from django.db.models import Count, Q, Avg
from django.urls import reverse
from django.utils import timezone
from django.core.paginator import Paginator
from django.core.exceptions import ValidationError
from datetime import datetime, timedelta
from django.contrib.auth import get_user_model
from .settings_service import get_profile_required_fields

USER_PROFILE_FIELDS = frozenset({'first_name', 'last_name'})

User = get_user_model()


def role_home_url_name(user=None, *, role=None):
    """Django URL name for the authenticated user's primary home page."""
    return 'core:dashboard'


def role_home_url(user=None, *, role=None):
    return reverse(role_home_url_name(user, role=role))


def analytics_home_url_name(user=None, *, role=None):
    """Django URL name for the analytics hub (admin hub lives at /)."""
    resolved_role = role or getattr(user, 'role', None)
    if resolved_role == 'admin':
        return 'core:dashboard'
    return 'analytics:dashboard'


def analytics_home_url(user=None, *, role=None):
    return reverse(analytics_home_url_name(user, role=role))


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
    elif user.role in ['staff', 'doctor', 'admin']:
        try:
            return user.staff_profile
        except StaffProfile.DoesNotExist:
            return None
    return None


def _profile_field_value(user, profile, field):
    if field in USER_PROFILE_FIELDS:
        return getattr(user, field, None)
    if profile is None:
        return None
    return getattr(profile, field, None)


def _profile_field_filled(value) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


def is_profile_complete(user):
    """Check if user's profile has all fields required for their role."""
    try:
        profile = get_user_profile(user)
        if not profile:
            return False

        required_fields = get_profile_required_fields(user.role)
        for field in required_fields:
            if not _profile_field_filled(_profile_field_value(user, profile, field)):
                return False
        return True
    except Exception:
        return False


# Human-readable labels for profile fields shown on the "profile required" page
FIELD_LABELS = {
    'first_name':        'First Name',
    'last_name':         'Last Name',
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

def get_missing_profile_fields(user):
    """Return a list of (field_name, friendly_label) tuples for missing required fields."""
    profile = get_user_profile(user)
    required_fields = get_profile_required_fields(user.role)
    if not required_fields:
        return []

    if not profile:
        return [(f, FIELD_LABELS.get(f, f.replace('_', ' ').title())) for f in required_fields]

    missing = []
    for field in required_fields:
        if not _profile_field_filled(_profile_field_value(user, profile, field)):
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


APPOINTMENT_NOTIFICATION_TRANSACTION_TYPES = frozenset({
    'appointment_reminder',
    'appointment_confirmed',
    'appointment_cancelled',
    'appointment_completed',
    'appointment_scheduled',
})

CERTIFICATE_NOTIFICATION_TRANSACTION_TYPES = frozenset({
    'certificate_requested',
    'certificate_processing',
    'certificate_approved',
    'certificate_ready',
    'certificate_rejected',
})


def resolve_notification_url(notification):
    """Return the detail/list URL for a notification, or None if unknown."""
    from django.urls import reverse

    transaction_type = notification.transaction_type
    related_id = notification.related_id

    if transaction_type in APPOINTMENT_NOTIFICATION_TRANSACTION_TYPES:
        if related_id:
            return reverse(
                'appointments:appointment_detail',
                kwargs={'appointment_id': related_id},
            )
        return reverse('appointments:appointment_list')

    if transaction_type in CERTIFICATE_NOTIFICATION_TRANSACTION_TYPES:
        return reverse('document_request:document_requests')

    if transaction_type in ('health_tip_new', 'health_tip_updated'):
        return reverse('health_tips:health_tips_list')

    if transaction_type in ('medical_record_created', 'medical_record_updated'):
        if related_id:
            return reverse(
                'medical_records:medical_record_detail_page',
                kwargs={'record_id': related_id},
            )
        return reverse('medical_records:medical_records')

    if transaction_type == 'feedback_request':
        return reverse('feedback:submit_feedback')

    if notification.notification_type == 'appointment' and related_id:
        return reverse(
            'appointments:appointment_detail',
            kwargs={'appointment_id': related_id},
        )

    if notification.notification_type == 'health_tip':
        return reverse('health_tips:health_tips_list')

    return None


def title_case_name(value):
    """Format a person name for display (each word title-cased, supports hyphens/apostrophes)."""
    if value is None:
        return ''
    text = str(value).strip()
    if not text:
        return text

    def _cap_token(token):
        if not token:
            return token
        return '-'.join(piece.capitalize() for piece in token.split('-'))

    words = []
    for word in text.split():
        if "'" in word:
            words.append("'".join(_cap_token(part) for part in word.split("'")))
        else:
            words.append(_cap_token(word))
    return ' '.join(words)


def student_name_field_q(term: str) -> Q:
    """Match one token against student first/last/middle name, email, or ID."""
    return (
        Q(first_name__icontains=term)
        | Q(last_name__icontains=term)
        | Q(email__icontains=term)
        | Q(student_profile__middle_name__icontains=term)
        | Q(student_profile__student_id__icontains=term)
    )


def student_search_q(query: str) -> Q:
    """Support single-field and multi-word full-name searches (e.g. \"Jane Doe\")."""
    q = (query or '').strip()
    if not q:
        return Q(pk__in=[])

    whole_phrase = student_name_field_q(q)
    terms = [part for part in re.split(r'\s+', q) if part]
    if len(terms) <= 1:
        return whole_phrase

    multi_word = Q()
    for term in terms:
        multi_word &= student_name_field_q(term)
    return whole_phrase | multi_word


def student_display_name(student):
    """Full student display name (first, middle, last) in title case."""
    profile = getattr(student, 'student_profile', None)
    parts = []
    if student.first_name:
        parts.append(title_case_name(student.first_name))
    if profile and profile.middle_name:
        parts.append(title_case_name(profile.middle_name))
    if student.last_name:
        parts.append(title_case_name(student.last_name))
    name = ' '.join(parts).strip()
    if name:
        return name
    fallback = student.get_full_name()
    return title_case_name(fallback) if fallback else student.email


def user_wants_in_app_notifications(user) -> bool:
    """Whether the user accepts in-app notification records."""
    if not getattr(user, 'is_authenticated', False):
        return False
    try:
        from .settings_service import get_user_preferences

        return get_user_preferences(user).in_app_notifications
    except Exception:
        return True


def create_notification(user, title, message, notification_type='general', related_id=None, transaction_type=None):
    """Create an in-app notification when the user has not opted out."""
    if not user_wants_in_app_notifications(user):
        return None

    from .models import Notification

    return Notification.objects.create(
        user=user,
        title=title,
        message=message,
        notification_type=notification_type,
        related_id=related_id,
        transaction_type=transaction_type,
    )


def create_bulk_notifications(users, title, message, notification_type='general', related_id=None, transaction_type=None):
    """Create in-app notifications for users who have not opted out."""
    from .models import Notification

    recipients = [user for user in users if user_wants_in_app_notifications(user)]
    if not recipients:
        return []

    notifications = [
        Notification(
            user=user,
            title=title,
            message=message,
            notification_type=notification_type,
            related_id=related_id,
            transaction_type=transaction_type,
        )
        for user in recipients
    ]
    return Notification.objects.bulk_create(notifications)


def notify_all_students(title, message, notification_type='general', related_id=None, transaction_type=None):
    """Send notification to all students (in-app and email per preferences)."""
    from .notification_delivery import deliver_bulk_notifications

    students = User.objects.filter(role='student')
    return deliver_bulk_notifications(
        students, title, message, notification_type, related_id, transaction_type
    )


def notify_all_staff(title, message, notification_type='general', related_id=None, transaction_type=None):
    """Send notification to all staff (in-app and email per preferences)."""
    from .notification_delivery import deliver_bulk_notifications

    staff = User.objects.filter(role__in=['staff', 'doctor'])
    return deliver_bulk_notifications(
        staff, title, message, notification_type, related_id, transaction_type
    )


def notify_all_users(title, message, notification_type='general', related_id=None, transaction_type=None):
    """Send notification to all users (in-app and email per preferences)."""
    from .notification_delivery import deliver_bulk_notifications

    users = User.objects.filter(role__in=['student', 'staff'])
    return deliver_bulk_notifications(
        users, title, message, notification_type, related_id, transaction_type
    )


def get_dashboard_stats(user):
    """Get dashboard statistics based on user role"""
    from appointments.models import Appointment
    from medical_records.models import MedicalRecord
    from document_request.models import DocumentRequest
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
            'pending_certificates': DocumentRequest.objects.filter(
                student=user,
                status=DocumentRequest.Status.PENDING_REVIEW,
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
            'pending_certificates': DocumentRequest.objects.filter(
                status=DocumentRequest.Status.PENDING_REVIEW,
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
            'pending_certificates': DocumentRequest.objects.filter(
                status=DocumentRequest.Status.PENDING_REVIEW,
            ).count(),
            'total_appointments': Appointment.objects.count(),
            'total_records': MedicalRecord.objects.count(),
            'total_certificates': DocumentRequest.objects.count(),
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
    from document_request.models import DocumentRequest
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
            'certificates': DocumentRequest.objects.filter(
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
            'pending_certificates': DocumentRequest.objects.filter(
                status=DocumentRequest.Status.PENDING_REVIEW,
            ).order_by('-created_at')[:limit],
        }
    
    elif user.role == 'admin':
        today = timezone.now().date()
        activity = {
            'recent_appointments': Appointment.objects.filter(
                date=today
            ).order_by('-created_at')[:limit],
            'recent_feedbacks': Feedback.objects.all().order_by('-created_at')[:limit],
            'recent_certificates': DocumentRequest.objects.all().order_by('-created_at')[:limit],
        }
    
    return activity


def get_weekly_stats():
    """Get weekly statistics for charts"""
    from appointments.models import Appointment
    from document_request.models import DocumentRequest
    
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
        'certificate_status': DocumentRequest.objects.values('status').annotate(
            count=Count('id')
        ).order_by('-count'),
    }


def get_client_ip(request):
    """Extract the client IP address from a Django request."""
    forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if forwarded_for:
        return forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', 'unknown')
