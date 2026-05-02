from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout, authenticate, login
from django.contrib import messages
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q, F
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.cache import cache
from django.conf import settings
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods
import re
import json
import hashlib
import logging
import secrets

from .models import (
    AccountProvisioningAudit,
    Notification,
    StudentProfile,
    StaffProfile,
    UserInvite,
    CourseProgram,
    CollegeDepartment,
    YearLevelOption,
)
from .forms import (
    StudentProfileForm,
    StaffProfileForm,
    AdminLoginForm,
    UserCreationForm,
    UserEditForm,
    PasswordResetForm,
    clean_strict_ph_number,
)
from .profile_policy import (
    STUDENT_PROFILE_REQUIRED_FIELDS,
    STAFF_PROFILE_REQUIRED_FIELDS,
    DOCTOR_PROFILE_REQUIRED_FIELDS,
)
from .utils import (
    get_user_profile, create_notification, paginate_queryset,
    create_bulk_notifications
)
from .decorators import admin_required, role_required

User = get_user_model()
MESSAGE_NOTIFICATION_TYPES = ("direct_message", "announcement_posted")
ADMIN_LOGIN_ATTEMPT_LIMIT = 5
ADMIN_LOGIN_LOCK_SECONDS = 900
auth_logger = logging.getLogger('security.auth')
INVITE_TOKEN_TTL_HOURS = getattr(settings, 'USER_INVITE_TOKEN_TTL_HOURS', 72)


def _get_client_ip(request):
    forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if forwarded_for:
        return forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', 'unknown')


def _admin_login_cache_key(request, email):
    fingerprint = f"{_get_client_ip(request)}:{(email or '').strip().lower()}"
    digest = hashlib.sha256(fingerprint.encode('utf-8')).hexdigest()
    return f"admin_login_failures:{digest}"


def _safe_login_redirect(request, target_url):
    require_https = bool(
        getattr(settings, 'ADMIN_LOGIN_REQUIRE_HTTPS_REDIRECT', False)
        or request.is_secure()
    )
    if target_url and url_has_allowed_host_and_scheme(
        url=target_url,
        allowed_hosts={request.get_host()},
        require_https=require_https,
    ):
        return target_url
    return reverse('core:dashboard')


def _hash_invite_token(raw_token):
    return hashlib.sha256(raw_token.encode('utf-8')).hexdigest()


def _create_user_invite(user, created_by):
    now = timezone.now()
    UserInvite.objects.filter(
        user=user,
        accepted_at__isnull=True,
        revoked_at__isnull=True,
    ).update(revoked_at=now)

    raw_token = secrets.token_urlsafe(32)
    invite = UserInvite.objects.create(
        user=user,
        created_by=created_by,
        token_hash=_hash_invite_token(raw_token),
        expires_at=now + timezone.timedelta(hours=INVITE_TOKEN_TTL_HOURS),
    )
    return invite, raw_token


def _log_provisioning_action(request, actor, target_user, action, metadata=None):
    AccountProvisioningAudit.objects.create(
        actor=actor,
        target_user=target_user,
        action=action,
        ip_address=_get_client_ip(request),
        metadata=metadata or {},
    )


def _year_levels_by_college():
    """Build mapping of college/department name to allowed year-level labels."""
    mapping = {}
    queryset = YearLevelOption.objects.filter(is_active=True).select_related('college_department')
    for item in queryset:
        mapping.setdefault(item.college_department.name, []).append(item.name)
    return mapping


OPTIONAL_COURSE_DEPARTMENTS = {
    'IBED - Primary',
    'IBED - Junior High School',
    'IBED - Junior Highschool',
}


def _is_course_optional_for_department(department_name):
    return (department_name or '').strip() in OPTIONAL_COURSE_DEPARTMENTS


# =====================
# Authentication Views
# =====================


@require_http_methods(["GET", "POST"])
def admin_login(request):
    """Dedicated password login endpoint for admin-role accounts."""
    if request.user.is_authenticated:
        return redirect('core:dashboard')

    requested_next = request.GET.get('next') if request.method == 'GET' else request.POST.get('next')
    redirect_to = _safe_login_redirect(request, requested_next)
    form = AdminLoginForm(request.POST or None)

    if request.method == 'POST':
        attempted_email = (request.POST.get('email') or '').strip().lower()
        client_ip = _get_client_ip(request)
        throttle_key = _admin_login_cache_key(request, attempted_email)
        failure_count = cache.get(throttle_key, 0)

        if failure_count >= ADMIN_LOGIN_ATTEMPT_LIMIT:
            auth_logger.warning(
                'admin_login_lockout_active email=%s ip=%s failures=%s',
                attempted_email,
                client_ip,
                failure_count,
            )
            form.add_error(None, 'Too many failed attempts. Try again in 15 minutes.')
        elif form.is_valid():
            credentials = {
                User.USERNAME_FIELD: form.cleaned_data['email'],
                'password': form.cleaned_data['password'],
            }
            user = authenticate(request, **credentials)

            is_admin_user = bool(
                user
                and user.is_active
                and (user.is_superuser or user.role == User.ROLE.ADMIN)
            )

            if not is_admin_user:
                updated_failures = failure_count + 1
                cache.set(throttle_key, updated_failures, ADMIN_LOGIN_LOCK_SECONDS)
                auth_logger.warning(
                    'admin_login_failed email=%s ip=%s failures=%s user_found=%s role=%s',
                    attempted_email,
                    client_ip,
                    updated_failures,
                    bool(user),
                    getattr(user, 'role', ''),
                )
                if updated_failures >= ADMIN_LOGIN_ATTEMPT_LIMIT:
                    auth_logger.warning(
                        'admin_login_lockout_triggered email=%s ip=%s failures=%s lock_seconds=%s',
                        attempted_email,
                        client_ip,
                        updated_failures,
                        ADMIN_LOGIN_LOCK_SECONDS,
                    )
                form.add_error(None, 'Invalid admin credentials.')
            else:
                cache.delete(throttle_key)
                login(request, user)
                auth_logger.info(
                    'admin_login_success user_id=%s email=%s ip=%s remember_me=%s',
                    user.id,
                    user.email,
                    client_ip,
                    bool(form.cleaned_data.get('remember_me')),
                )
                if not form.cleaned_data.get('remember_me'):
                    request.session.set_expiry(0)
                return redirect(redirect_to)

    return render(
        request,
        'core/admin_login.html',
        {
            'form': form,
            'next': redirect_to,
        },
    )

def logout_view(request):
    """Handle user logout"""
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('account_login')


@require_http_methods(["GET", "POST"])
def accept_invite(request, token):
    """Accept a user invitation and activate account when invite is valid."""
    invite = UserInvite.objects.select_related('user').filter(
        token_hash=_hash_invite_token(token)
    ).first()

    if not invite:
        return render(request, 'core/invite_accept.html', {'invite_state': 'invalid'})

    user = invite.user
    now = timezone.now()

    if invite.revoked_at:
        return render(request, 'core/invite_accept.html', {'invite_state': 'revoked'})
    if invite.accepted_at:
        return render(request, 'core/invite_accept.html', {'invite_state': 'accepted', 'invited_user': user})
    if invite.expires_at <= now:
        return render(request, 'core/invite_accept.html', {'invite_state': 'expired', 'invited_user': user})
    if user.onboarding_status == User.ONBOARDING_STATUS.ACTIVE and user.is_active:
        return render(request, 'core/invite_accept.html', {'invite_state': 'already_active', 'invited_user': user})

    if request.method == 'POST':
        with transaction.atomic():
            invite.accepted_at = now
            invite.save(update_fields=['accepted_at', 'updated_at'])
            UserInvite.objects.filter(
                user=user,
                accepted_at__isnull=True,
                revoked_at__isnull=True,
            ).exclude(pk=invite.pk).update(revoked_at=now)

            user.is_active = True
            user.onboarding_status = User.ONBOARDING_STATUS.ACTIVE
            user.save(update_fields=['is_active', 'onboarding_status'])

            create_notification(
                user=user,
                title='Invitation Accepted',
                message='Your account invitation has been accepted and your account is now active.',
                notification_type='general'
            )

        messages.success(request, 'Invitation accepted. You can now sign in.')
        return redirect('account_login')

    context = {
        'invite_state': 'ready',
        'invited_user': user,
        'expires_at': invite.expires_at,
    }
    return render(request, 'core/invite_accept.html', context)


@login_required
def profile_required(request):
    """View to show profile completion required page – access to all services is blocked."""
    from .utils import get_missing_profile_fields
    # Returns a list of (field_name, friendly_label) tuples
    missing = get_missing_profile_fields(request.user)
    # Pass only the labels to the template
    missing_labels = [label for _field, label in missing]
    return render(request, 'core/profile_required.html', {
        'missing_fields': missing_labels,
    })


# =====================
# Dashboard Views
# =====================

@login_required
def dashboard(request):
    """Main dashboard view - role-based content"""
    from appointments.models import Appointment
    from medical_records.models import MedicalRecord
    from document_request.models import DocumentRequest as CertificateRequest
    
    context = {}
    
    if request.user.role == 'student':
        context.update({
            'upcoming_appointments': Appointment.objects.filter(
                student=request.user, 
                date__gte=timezone.now().date(),
                status__in=['pending', 'confirmed']
            ).order_by('date', 'time')[:3],
            'recent_records': MedicalRecord.objects.filter(
                student=request.user
            ).order_by('-created_at')[:3],
            'unread_notifications': Notification.objects.filter(
                user=request.user, 
                is_read=False
            ).exclude(
                transaction_type__in=MESSAGE_NOTIFICATION_TYPES
            ).count(),
            'pending_certificates': CertificateRequest.objects.filter(
                student=request.user,
                status='pending'
            ).count(),
            'total_appointments': Appointment.objects.filter(student=request.user).count(),
            'total_records': MedicalRecord.objects.filter(student=request.user).count(),
            'approved_certificates': CertificateRequest.objects.filter(
                student=request.user,
                status='approved'
            ).count(),
        })
    
    elif request.user.role == 'doctor':
        today = timezone.now().date()
        context.update({
            'today_appointments': Appointment.objects.filter(
                doctor=request.user,
                date=today
            ).order_by('time'),
            'pending_appointments': Appointment.objects.filter(
                doctor=request.user,
                status='pending'
            ).count(),
            'pending_certificates': CertificateRequest.objects.filter(
                status='pending'
            ).count(),
            'total_patients': MedicalRecord.objects.filter(
                doctor=request.user
            ).values('student').distinct().count(),
            'completed_appointments': Appointment.objects.filter(
                doctor=request.user,
                status='completed'
            ).count(),
            'recent_records': MedicalRecord.objects.filter(
                doctor=request.user
            ).order_by('-created_at')[:5],
        })

    elif request.user.role == 'staff':
        today = timezone.now().date()
        context.update({
            'today_appointments': Appointment.objects.filter(
                date=today
            ).order_by('time'),
            'pending_appointments': Appointment.objects.filter(
                status='pending'
            ).count(),
            'total_patients': MedicalRecord.objects.values('student').distinct().count(),
            'completed_appointments': Appointment.objects.filter(
                status='completed'
            ).count(),
            'recent_records': MedicalRecord.objects.order_by('-created_at')[:5],
        })
    
    elif request.user.role == 'admin':
        from appointments.models import Appointment
        from document_request.models import DocumentRequest as CertificateRequest
        from health_forms_services.models import HealthProfileForm, DentalHealthForm
        from pharmacy.models import Medicine, Batch
        
        total_students = User.objects.filter(role='student').count()
        total_staff = User.objects.filter(role='staff').count()
        total_doctors = User.objects.filter(role='doctor').count()
        total_admins = User.objects.filter(role='admin').count()
        
        # Pending items needing admin attention
        pending_health_forms = HealthProfileForm.objects.filter(status='pending').count()
        pending_dental_forms = DentalHealthForm.objects.filter(status='pending').count()
        pending_certs = CertificateRequest.objects.filter(status='pending').count()
        pending_reviews = pending_health_forms + pending_dental_forms
        
        # Stale / inactive users
        stale_pending = User.objects.filter(
            onboarding_status='pending_activation',
            is_deleted=False,
        ).count()
        inactive_users = User.objects.filter(is_active=False, is_deleted=False).count()
        
        # Pharmacy alerts
        low_stock = Medicine.objects.filter(
            is_active=True,
        ).filter(
            batches__quantity__lte=F('reorder_level'),
        ).distinct().count() if hasattr(Medicine, 'reorder_level') else 0
        
        # Operations
        total_appointments = Appointment.objects.count()
        today = timezone.now().date()
        today_appointments = Appointment.objects.filter(date=today).count()
        
        context.update({
            # KPI row
            'total_users': User.objects.count(),
            'total_students': total_students,
            'total_staff': total_staff,
            'total_doctors': total_doctors,
            'total_admins': total_admins,
            'active_users': User.objects.filter(is_active=True, is_deleted=False).count(),
            # Operations
            'total_appointments': total_appointments,
            'today_appointments': today_appointments,
            'pending_certificates': pending_certs,
            'active_doctors': total_doctors,
            # Attention items
            'pending_reviews': pending_reviews,
            'pending_health_forms': pending_health_forms,
            'pending_dental_forms': pending_dental_forms,
            'stale_pending_users': stale_pending,
            'inactive_users': inactive_users,
            'low_stock_medicines': low_stock,
        })

    return render(request, 'core/dashboard.html', context)


# =====================
# Notification Views
# =====================

@login_required
def notifications(request):
    """Display user notifications"""
    notifications_qs = Notification.objects.filter(user=request.user).exclude(
        transaction_type__in=MESSAGE_NOTIFICATION_TYPES
    ).order_by('-created_at')
    
    # Filter by read/unread status
    status = request.GET.get('status')
    if status == 'unread':
        notifications_qs = notifications_qs.filter(is_read=False)
    elif status == 'read':
        notifications_qs = notifications_qs.filter(is_read=True)
    
    # Filter by type
    notification_type = request.GET.get('type')
    if notification_type:
        notifications_qs = notifications_qs.filter(notification_type=notification_type)
    
    # Mark all as read if requested
    if request.GET.get('mark_all_read') == 'true':
        notifications_qs.filter(is_read=False).update(is_read=True)
        messages.success(request, 'All notifications marked as read.')
        return redirect('core:notifications')
    
    paginator = Paginator(notifications_qs, 15)
    page = request.GET.get('page')
    notifications_page = paginator.get_page(page)
    
    # Get counts for filters
    total_count = Notification.objects.filter(user=request.user).exclude(
        transaction_type__in=MESSAGE_NOTIFICATION_TYPES
    ).count()
    unread_count = Notification.objects.filter(user=request.user, is_read=False).exclude(
        transaction_type__in=MESSAGE_NOTIFICATION_TYPES
    ).count()
    read_count = total_count - unread_count
    
    context = {
        'notifications': notifications_page,
        'total_count': total_count,
        'unread_count': unread_count,
        'read_count': read_count,
        'current_status': status,
        'current_type': notification_type,
    }
    
    return render(request, 'core/notifications.html', context)


@login_required
def mark_notification_read(request, notification_id):
    """Mark single notification as read"""
    notification = get_object_or_404(Notification, id=notification_id, user=request.user)
    notification.is_read = True
    notification.save()
    
    return JsonResponse({'status': 'success'})


@login_required
def mark_all_notifications_read(request):
    """Mark all notifications as read for the current user"""
    if request.method == 'POST':
        updated_count = Notification.objects.filter(user=request.user, is_read=False).exclude(
            transaction_type__in=MESSAGE_NOTIFICATION_TYPES
        ).update(is_read=True)
        return JsonResponse({
            'status': 'success', 
            'message': f'{updated_count} notifications marked as read'
        })
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'})


@login_required
def clear_all_notifications(request):
    """Delete all notifications for the current user"""
    if request.method == 'POST':
        notifications_qs = Notification.objects.filter(user=request.user).exclude(
            transaction_type__in=MESSAGE_NOTIFICATION_TYPES
        )
        deleted_count = notifications_qs.count()
        notifications_qs.delete()
        return JsonResponse({
            'status': 'success', 
            'message': f'{deleted_count} notifications cleared',
            'count': deleted_count
        })
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'})


@login_required
@admin_required
def create_system_notification(request):
    """Allow admins to create system-wide notifications"""
    
    if request.method == 'POST':
        title = request.POST.get('title')
        message = request.POST.get('message')
        notification_type = request.POST.get('notification_type', 'general')
        recipient_type = request.POST.get('recipient_type', 'all')
        
        if not title or not message:
            messages.error(request, 'Title and message are required.')
            return render(request, 'core/create_system_notification.html')
        
        # Determine recipients
        if recipient_type == 'students':
            recipients = User.objects.filter(role='student')
        elif recipient_type == 'staff_only':
            recipients = User.objects.filter(role='staff')
        elif recipient_type == 'doctors':
            recipients = User.objects.filter(role='doctor')
        elif recipient_type == 'admins':
            recipients = User.objects.filter(role='admin')
        elif recipient_type == 'staff_and_doctors':
            recipients = User.objects.filter(role__in=['staff', 'doctor'])
        elif recipient_type == 'non_students':
            recipients = User.objects.filter(role__in=['staff', 'doctor', 'admin'])
        else:  # all
            recipients = User.objects.filter(role__in=['student', 'staff', 'doctor', 'admin'])
        
        # Create notifications
        created_count = len(create_bulk_notifications(recipients, title, message, notification_type))
        
        messages.success(request, 'Notification sent successfully.')
        return redirect('core:notifications')
    
    return render(request, 'core/create_system_notification.html')


# =====================
# Profile Views
# =====================

@login_required
def profile_view(request):
    """Display user profile information with related dental and medical records"""
    from dental_records.models import DentalRecord
    
    profile = get_user_profile(request.user)
    
    # Get the latest dental record for the user
    dental_record = None
    try:
        dental_record = DentalRecord.objects.filter(patient=request.user).select_related(
            'vital_signs', 'health_questionnaire', 'systems_review'
        ).latest('created_at')
    except DentalRecord.DoesNotExist:
        pass
    
    # Calculate profile completion percentage
    completion_percentage = 0
    if profile:
        if request.user.role == 'student':
            required_fields = STUDENT_PROFILE_REQUIRED_FIELDS
        elif request.user.role == 'doctor':
            required_fields = DOCTOR_PROFILE_REQUIRED_FIELDS
        else:
            required_fields = STAFF_PROFILE_REQUIRED_FIELDS
        
        filled_count = 0
        for field in required_fields:
            if field in {'first_name', 'last_name'}:
                value = getattr(request.user, field, None)
            else:
                value = getattr(profile, field, None)
            if value and (not isinstance(value, str) or value.strip()):
                filled_count += 1
        completion_percentage = int((filled_count / len(required_fields)) * 100)
    
    course_queryset = CourseProgram.objects.filter(is_active=True).select_related('college_department')
    course_options = list(course_queryset.values_list('name', flat=True))
    college_options = list(
        CollegeDepartment.objects.filter(is_active=True)
        .values_list('name', flat=True)
    )
    year_level_options_by_college = _year_levels_by_college()
    active_college = profile.department if profile and request.user.role == 'student' else ''
    year_level_options = year_level_options_by_college.get(active_college, [])
    course_options_by_college = {}
    for course in course_queryset:
        college_name = course.college_department.name
        course_options_by_college.setdefault(college_name, []).append(course.name)

    context = {
        'user': request.user,
        'profile': profile,
        'dental_record': dental_record,
        'completion_percentage': completion_percentage,
        'course_options': course_options,
        'college_options': college_options,
        'course_options_by_college_json': json.dumps(course_options_by_college),
        'college_options_json': json.dumps(college_options),
        'year_level_options': year_level_options,
        'year_level_options_by_college_json': json.dumps(year_level_options_by_college),
    }
    
    return render(request, 'core/profile.html', context)


@login_required
def quick_edit_profile(request):
    """Quick edit a single profile field via AJAX/form submission"""
    is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest'

    if request.method != 'POST':
        if is_ajax:
            return JsonResponse({'success': False, 'error': 'Invalid request method.'}, status=405)
        messages.error(request, 'Invalid request method.')
        return redirect('core:profile')
    
    profile = get_user_profile(request.user)
    if not profile:
        if is_ajax:
            return JsonResponse({'success': False, 'error': 'Profile not found. Please complete your profile first.'}, status=404)
        messages.error(request, 'Profile not found. Please complete your profile first.')
        return redirect('core:edit_profile')
    
    field_name = request.POST.get('field_name')
    field_value = request.POST.get('field_value', '').strip()
    selected_college = request.POST.get('selected_college', '').strip()

    if field_name == 'academic_bundle':
        if request.user.role != 'student':
            if is_ajax:
                return JsonResponse({'success': False, 'error': 'Academic quick edit is only available for students.'}, status=400)
            messages.error(request, 'Academic quick edit is only available for students.')
            return redirect('core:profile')

        department = request.POST.get('department', '').strip()
        year_level = request.POST.get('year_level', '').strip()
        course = request.POST.get('course', '').strip()

        try:
            valid_colleges = set(
                CollegeDepartment.objects.filter(is_active=True)
                .values_list('name', flat=True)
            )
            if department not in valid_colleges:
                raise ValueError('Invalid College selection.')

            course_is_optional = _is_course_optional_for_department(department)
            if not course and not course_is_optional:
                raise ValueError('Course/Program is required.')

            valid_courses = set(
                CourseProgram.objects.filter(
                    is_active=True,
                    college_department__name=department,
                ).values_list('name', flat=True)
            )
            if course and course not in valid_courses:
                raise ValueError('Invalid Course/Program for selected College.')

            valid_year_levels = set(
                YearLevelOption.objects.filter(
                    is_active=True,
                    college_department__name=department,
                ).values_list('name', flat=True)
            )
            if year_level not in valid_year_levels:
                raise ValueError('Invalid Year Level for selected College.')

            profile.department = department
            profile.year_level = year_level
            profile.course = course
            profile.save(update_fields=['department', 'year_level', 'course'])

            session_key = f'profile_complete_{request.user.id}_{request.user.role}'
            if session_key in request.session:
                del request.session[session_key]
            legacy_key = f'profile_complete_{request.user.id}'
            if legacy_key in request.session:
                del request.session[legacy_key]

            if is_ajax:
                return JsonResponse({
                    'success': True,
                    'message': 'Academic information updated successfully.',
                    'field_name': 'academic_bundle',
                    'academic_payload': {
                        'department': department,
                        'year_level': year_level,
                        'course': course,
                    },
                })

            messages.success(request, 'Academic information updated successfully.')
            return redirect('core:profile')
        except ValueError as e:
            if is_ajax:
                return JsonResponse({'success': False, 'error': f'Error updating field: {str(e)}'}, status=400)
            messages.error(request, f'Error updating field: {str(e)}')
            return redirect('core:profile')
    
    # Define allowed fields for quick edit (security measure)
    allowed_fields = [
        'academic_bundle',
        'first_name', 'last_name',
        'phone', 'telephone_number', 'emergency_contact', 'emergency_phone',
        'address', 'allergies', 'medical_conditions', 'middle_name',
        'place_of_birth', 'age', 'course', 'year_level', 'department', 'position',
        'specialization'
    ]

    if request.user.role == 'doctor':
        doctor_blocked_fields = {'allergies', 'medical_conditions', 'blood_type'}
        allowed_fields = [f for f in allowed_fields if f not in doctor_blocked_fields]
    elif request.user.role == 'admin':
        admin_blocked_fields = {
            'allergies',
            'medical_conditions',
            'blood_type',
            'department',
            'position',
            'specialization',
        }
        allowed_fields = [f for f in allowed_fields if f not in admin_blocked_fields]
    
    # Fields that need special handling
    date_fields = ['date_of_birth']
    integer_fields = ['age']
    select_fields = ['gender', 'civil_status', 'blood_type']

    if request.user.role == 'admin':
        select_fields = [f for f in select_fields if f != 'blood_type']
    
    all_allowed = allowed_fields + date_fields + select_fields
    
    if field_name not in all_allowed:
        if is_ajax:
            return JsonResponse({'success': False, 'error': 'This field cannot be edited via quick edit.'}, status=400)
        messages.error(request, 'This field cannot be edited via quick edit.')
        return redirect('core:profile')
    
    user_fields = {'first_name', 'last_name'}
    target_obj = request.user if field_name in user_fields else profile

    # Validate the field exists on target model
    if not hasattr(target_obj, field_name):
        if is_ajax:
            return JsonResponse({'success': False, 'error': 'Invalid field.'}, status=400)
        messages.error(request, 'Invalid field.')
        return redirect('core:profile')
    
    try:
        text_max_lengths = {
            'address': 500,
            'place_of_birth': 200,
            'course': 100,
            'year_level': 20,
            'department': 100,
            'position': 100,
            'specialization': 100,
        }

        if field_name == 'address':
            # Keep intentional newlines but normalize surrounding whitespace.
            field_value = '\n'.join(line.strip() for line in field_value.splitlines()).strip()
            if not field_value:
                raise ValueError('Address is required.')
            if len(field_value) < 5:
                raise ValueError('Address must be at least 5 characters.')

        if field_name in ['first_name', 'last_name']:
            field_value = ' '.join(field_value.split())
            if not field_value:
                raise ValueError(f'{field_name.replace("_", " ").title()} is required.')
            if len(field_value) > 150:
                raise ValueError(f'{field_name.replace("_", " ").title()} must be 150 characters or fewer.')
            if not re.fullmatch(r"[A-Za-z][A-Za-z .'-]*", field_value):
                raise ValueError(f'{field_name.replace("_", " ").title()} contains invalid characters.')

        if field_name == 'middle_name':
            field_value = ' '.join(field_value.split())
            if field_value and len(field_value) > 100:
                raise ValueError('Middle Name must be 100 characters or fewer.')
            if field_value and not re.fullmatch(r"[A-Za-z][A-Za-z .'-]*", field_value):
                raise ValueError('Middle Name contains invalid characters.')

        if field_name in ['allergies', 'medical_conditions']:
            list_parts = re.split(r'[\n,;]+', field_value)
            clean_parts = []
            for part in list_parts:
                item = part.strip()
                if not item:
                    continue
                if len(item) > 120:
                    raise ValueError('Each list item must be 120 characters or fewer.')
                if item not in clean_parts:
                    clean_parts.append(item)

            if len(clean_parts) > 30:
                raise ValueError('Maximum 30 items allowed.')

            # Store as newline-delimited list for stable parsing/display.
            field_value = '\n'.join(clean_parts)

        if request.user.role == 'student' and field_name in ['course', 'year_level', 'department']:
            selected_college_name = selected_college or profile.department
            course_is_optional = _is_course_optional_for_department(selected_college_name)

            if not field_value and not (field_name == 'course' and course_is_optional):
                raise ValueError(f'{field_name.replace("_", " ").title()} is required.')

            if field_name == 'course':
                if not selected_college_name:
                    raise ValueError('Select College first before selecting Course/Program.')

                # Prevent bypass: selected college must match persisted student college.
                if profile.department and selected_college and selected_college != profile.department:
                    raise ValueError('Selected college does not match your saved College. Update College first.')

                valid_courses = set(
                    CourseProgram.objects.filter(
                        is_active=True,
                        college_department__name=selected_college_name,
                    ).values_list('name', flat=True)
                )
                if field_value and field_value not in valid_courses:
                    raise ValueError('Invalid Course/Program for selected College.')

            if field_name == 'year_level':
                selected_college_name = selected_college or profile.department
                if not selected_college_name:
                    raise ValueError('Select College first before selecting Year Level.')

                valid_year_levels = set(
                    YearLevelOption.objects.filter(
                        is_active=True,
                        college_department__name=selected_college_name,
                    ).values_list('name', flat=True)
                )
                if field_value not in valid_year_levels:
                    raise ValueError('Invalid Year Level for selected College.')

            if field_name == 'department':
                valid_colleges = set(
                    CollegeDepartment.objects.filter(is_active=True)
                    .values_list('name', flat=True)
                )
                if field_value not in valid_colleges:
                    raise ValueError('Invalid College selection.')

                # Keep student course consistent with selected college.
                if request.user.role == 'student' and profile.course:
                    valid_courses = set(
                        CourseProgram.objects.filter(
                            is_active=True,
                            college_department__name=field_value,
                        ).values_list('name', flat=True)
                    )
                    if profile.course not in valid_courses:
                        profile.course = ''
                        profile.save(update_fields=['course'])

                if request.user.role == 'student' and profile.year_level:
                    valid_year_levels = set(
                        YearLevelOption.objects.filter(
                            is_active=True,
                            college_department__name=field_value,
                        ).values_list('name', flat=True)
                    )
                    if profile.year_level not in valid_year_levels:
                        profile.year_level = ''
                        profile.save(update_fields=['year_level'])

        if field_name in ['phone', 'telephone_number', 'emergency_phone']:
            phone_required = field_name == 'phone' or (
                field_name == 'emergency_phone' and request.user.role == 'student'
            )
            field_value = clean_strict_ph_number(field_value, required=phone_required)

        if field_name in ['gender', 'civil_status', 'blood_type']:
            valid_choices = {
                'gender': {'male', 'female', 'other', ''},
                'civil_status': {'single', 'married', 'widowed', 'separated', ''},
                'blood_type': {'A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-', ''},
            }
            if field_value not in valid_choices[field_name]:
                raise ValueError(f'Invalid value for {field_name.replace("_", " ").title()}.')

        if field_name in text_max_lengths and len(field_value) > text_max_lengths[field_name]:
            raise ValueError(
                f'{field_name.replace("_", " ").title()} must be '
                f'{text_max_lengths[field_name]} characters or fewer.'
            )

        # Handle date fields
        if field_name in date_fields:
            if field_value:
                from datetime import datetime
                field_value = datetime.strptime(field_value, '%Y-%m-%d').date()
                if field_value > timezone.now().date():
                    raise ValueError('Date of Birth cannot be in the future.')
            else:
                field_value = None
        elif field_name in integer_fields:
            if field_value:
                field_value = int(field_value)
                if field_value < 0 or field_value > 150:
                    raise ValueError('Age must be between 0 and 150.')
            else:
                field_value = None
        
        # Set the value
        setattr(target_obj, field_name, field_value)
        target_obj.save()

        raw_value = getattr(target_obj, field_name, '')
        if raw_value is None:
            raw_value = ''

        display_value = raw_value
        if field_name == 'gender':
            display_value = profile.get_gender_display() if raw_value else 'Not specified'
        elif field_name == 'civil_status':
            display_value = profile.get_civil_status_display() if raw_value else 'Not specified'
        elif field_name == 'blood_type':
            display_value = raw_value or '--'
        elif field_name == 'date_of_birth':
            display_value = raw_value.strftime('%B %d, %Y') if raw_value else 'Not specified'
            raw_value = raw_value.strftime('%Y-%m-%d') if raw_value else ''
        elif field_name == 'age':
            display_value = f'{raw_value} years old' if raw_value else 'Not specified'
        
        # Clear profile completion cache
        session_key = f'profile_complete_{request.user.id}_{request.user.role}'
        if session_key in request.session:
            del request.session[session_key]
        legacy_key = f'profile_complete_{request.user.id}'
        if legacy_key in request.session:
            del request.session[legacy_key]
        
        success_message = f'Successfully updated your {field_name.replace("_", " ").title()}.'
        if is_ajax:
            full_name = (
                f"{request.user.first_name} {profile.middle_name} {request.user.last_name}"
                .replace('  ', ' ')
                .strip()
                .upper()
            )
            return JsonResponse({
                'success': True,
                'message': success_message,
                'field_name': field_name,
                'raw_value': raw_value,
                'display_value': display_value,
                'full_name': full_name,
            })

        messages.success(request, success_message)
    except (ValueError, ValidationError) as e:
        error_text = str(e)
        if error_text.startswith("['") and error_text.endswith("']"):
            error_text = error_text[2:-2]
        if is_ajax:
            return JsonResponse({'success': False, 'error': f'Error updating field: {error_text}'}, status=400)
        messages.error(request, f'Error updating field: {error_text}')
    except Exception as e:
        if is_ajax:
            return JsonResponse({'success': False, 'error': f'Error updating field: {str(e)}'}, status=400)
        messages.error(request, f'Error updating field: {str(e)}')
    
    return redirect('core:profile')


@login_required
def edit_profile(request):
    """Edit user profile information"""
    from dental_records.models import DentalRecord
    
    profile = get_user_profile(request.user)
    is_first_time = profile is None
    
    if request.user.role == 'student':
        form_class = StudentProfileForm
    elif request.user.role in ['staff', 'doctor', 'admin']:
        form_class = StaffProfileForm
    else:
        messages.error(request, 'Profile editing not available for your role.')
        return redirect('core:dashboard')
    
    # Check for dental record to auto-fill data
    dental_record = None
    try:
        dental_record = DentalRecord.objects.filter(patient=request.user).latest('created_at')
    except DentalRecord.DoesNotExist:
        pass
    
    if request.method == 'POST':
        # Handle auto-fill request
        if 'autofill_from_dental' in request.POST and dental_record:
            # Create initial data from dental record
            initial_data = {}
            
            if dental_record.middle_name:
                initial_data['middle_name'] = dental_record.middle_name
            if dental_record.gender:
                initial_data['gender'] = dental_record.gender
            if dental_record.civil_status:
                initial_data['civil_status'] = dental_record.civil_status
            if dental_record.date_of_birth:
                initial_data['date_of_birth'] = dental_record.date_of_birth
            if dental_record.place_of_birth:
                initial_data['place_of_birth'] = dental_record.place_of_birth
            if dental_record.age:
                initial_data['age'] = dental_record.age
            if dental_record.address:
                initial_data['address'] = dental_record.address
            if dental_record.contact_number:
                initial_data['phone'] = dental_record.contact_number
            if dental_record.telephone_number:
                initial_data['telephone_number'] = dental_record.telephone_number
            if dental_record.guardian_name:
                initial_data['emergency_contact'] = dental_record.guardian_name
            if dental_record.guardian_contact:
                initial_data['emergency_phone'] = dental_record.guardian_contact
            if dental_record.department_college_office:
                if request.user.role == 'student':
                    # Try to parse as course
                    initial_data['course'] = dental_record.department_college_office
                else:
                    initial_data['department'] = dental_record.department_college_office
            
            # Merge with existing profile data if available
            if profile:
                if request.user.role in ['staff', 'doctor', 'admin']:
                    form = form_class(initial=initial_data, instance=profile, user=request.user)
                else:
                    form = form_class(initial=initial_data, instance=profile)
                # Update form with autofilled values
                for key, value in initial_data.items():
                    if key in form.fields:
                        form.initial[key] = value
            else:
                if request.user.role in ['staff', 'doctor', 'admin']:
                    form = form_class(initial=initial_data, user=request.user)
                else:
                    form = form_class(initial=initial_data)
            
            messages.success(request, 'Profile auto-filled from your dental record. Please review and save.')
            
        else:
            # Normal form submission
            first_name = ' '.join((request.POST.get('first_name') or '').split())
            last_name = ' '.join((request.POST.get('last_name') or '').split())
            names_valid = True
            if not first_name or not last_name:
                messages.error(request, 'First Name and Last Name are required.')
                names_valid = False
                if request.user.role in ['staff', 'doctor', 'admin']:
                    form = form_class(request.POST, request.FILES, instance=profile, user=request.user)
                else:
                    form = form_class(request.POST, request.FILES, instance=profile)
            elif request.user.role in ['staff', 'doctor', 'admin']:
                form = form_class(request.POST, request.FILES, instance=profile, user=request.user)
            else:
                form = form_class(request.POST, request.FILES, instance=profile)
            if names_valid and form.is_valid():
                request.user.first_name = first_name
                request.user.last_name = last_name
                request.user.save(update_fields=['first_name', 'last_name'])

                profile = form.save(commit=False)
                if not profile.user_id:
                    profile.user = request.user
                profile.save()
                
                # Clear profile completion cache
                session_key = f'profile_complete_{request.user.id}_{request.user.role}'
                if session_key in request.session:
                    del request.session[session_key]
                legacy_key = f'profile_complete_{request.user.id}'
                if legacy_key in request.session:
                    del request.session[legacy_key]
                
                if is_first_time:
                    messages.success(request, 'Welcome! Your profile has been created successfully!')
                    # Clear the welcome shown flag
                    request.session.pop('profile_welcome_shown', None)
                else:
                    messages.success(request, 'Profile updated successfully!')
                
                # Redirect to profile page after successful save
                return redirect('core:profile')
            else:
                if is_first_time:
                    messages.error(request, 'Please complete all required fields to set up your profile.')
                else:
                    messages.error(request, 'Please correct the errors below.')
    else:
        if request.user.role in ['staff', 'doctor', 'admin']:
            form = form_class(instance=profile, user=request.user)
        else:
            form = form_class(instance=profile)
        
        # Only show welcome message for first-time users, and only once per session
        if is_first_time and not request.session.get('profile_welcome_shown'):
            messages.info(request, 
                f'Welcome to JMCFI Clinic! Please complete your profile to get started.')
            request.session['profile_welcome_shown'] = True
    
    course_queryset = CourseProgram.objects.filter(is_active=True).select_related('college_department')
    college_options = list(
        CollegeDepartment.objects.filter(is_active=True)
        .values_list('name', flat=True)
    )
    course_options_by_college = {}
    for course in course_queryset:
        college_name = course.college_department.name
        course_options_by_college.setdefault(college_name, []).append(course.name)

    year_level_options_by_college = _year_levels_by_college()
    selected_department = ''
    if request.user.role == 'student' and 'department' in form.fields:
        selected_department = (form['department'].value() or '').strip()
    initial_course_options = course_options_by_college.get(selected_department, [])
    initial_year_level_options = year_level_options_by_college.get(selected_department, [])

    context = {
        'form': form,
        'profile': profile,
        'user': request.user,
        'is_first_time': is_first_time,
        'dental_record': dental_record,
        'college_options': college_options,
        'initial_course_options': initial_course_options,
        'initial_year_level_options': initial_year_level_options,
        'college_options_json': json.dumps(college_options),
        'course_options_by_college_json': json.dumps(course_options_by_college),
        'year_level_options_by_college_json': json.dumps(year_level_options_by_college),
    }
    
    return render(request, 'core/edit_profile.html', context)


# =====================
# User Management Views (Admin Only)
# =====================

@login_required
@admin_required
def user_management(request):
    """List all users with filtering and search"""
    from appointments.models import Appointment
    from medical_records.models import MedicalRecord
    from document_request.models import DocumentRequest as CertificateRequest
    
    # Get filter parameters
    role_filter = request.GET.get('role', '')
    status_filter = request.GET.get('status', '')
    search_query = request.GET.get('search', '')
    
        # Base queryset - exclude soft-deleted users by default
    users = User.objects.filter(is_deleted=False).order_by('-date_joined')
    
    # Apply filters
    if role_filter:
        users = users.filter(role=role_filter)
    
    if status_filter == 'active':
        users = users.filter(
            onboarding_status=User.ONBOARDING_STATUS.ACTIVE,
            is_active=True,
        )
    elif status_filter == 'pending':
        users = users.filter(onboarding_status=User.ONBOARDING_STATUS.PENDING_ACTIVATION)
    elif status_filter == 'suspended':
        users = users.filter(onboarding_status=User.ONBOARDING_STATUS.SUSPENDED)
    elif status_filter == 'inactive':
        # Legacy filter value retained for compatibility with existing links/bookmarks.
        users = users.filter(is_active=False)
    elif status_filter == 'deleted':
        # Show soft-deleted users
        users = User.objects.filter(is_deleted=True).order_by('-deleted_at')
    
    # Apply search
    if search_query:
        users = users.filter(
            Q(username__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query)
        )
    
    # Get statistics
    stats = {
        'total_users': User.objects.count(),
        'total_appointments': Appointment.objects.count(),
        'pending_certificates': CertificateRequest.objects.filter(status='pending').count(),
        'active_doctors': User.objects.filter(role='doctor').count(),
        'total_students': User.objects.filter(role='student').count(),
        'total_staff': User.objects.filter(role__in=['staff', 'doctor']).count(),
        'total_admins': User.objects.filter(role='admin').count(),
        'active_users': User.objects.filter(is_active=True).count(),
        'inactive_users': User.objects.filter(is_active=False).count(),
    }
    
    # Paginate results
    users = paginate_queryset(users, request, per_page=20)
    
    context = {
        'users': users,
        'stats': stats,
        'role_filter': role_filter,
        'status_filter': status_filter,
        'search_query': search_query,
    }
    
    return render(request, 'core/user_management/user_list.html', context)


@login_required
@admin_required
def user_detail(request, user_id):
    """View detailed information about a specific user"""
    from appointments.models import Appointment
    from medical_records.models import MedicalRecord
    from document_request.models import DocumentRequest as CertificateRequest
    
    user = get_object_or_404(User, id=user_id)
    profile = get_user_profile(user)
    
    # Get user statistics
    if user.role == 'student':
        stats = {
            'Total Appointments': Appointment.objects.filter(student=user).count(),
            'Completed Appointments': Appointment.objects.filter(student=user, status='completed').count(),
            'Pending Appointments': Appointment.objects.filter(student=user, status='pending').count(),
            'Medical Records': MedicalRecord.objects.filter(student=user).count(),
            'Certificate Requests': CertificateRequest.objects.filter(student=user).count(),
        }
        recent_activity = {
            'appointments': Appointment.objects.filter(student=user).order_by('-created_at')[:5],
            'medical_records': MedicalRecord.objects.filter(student=user).order_by('-created_at')[:5],
        }
    elif user.role == 'staff':
        stats = {
            'Total Appointments': Appointment.objects.filter(doctor=user).count(),
            'Completed Appointments': Appointment.objects.filter(doctor=user, status='completed').count(),
            'Pending Appointments': Appointment.objects.filter(doctor=user, status='pending').count(),
            'Medical Records': MedicalRecord.objects.filter(doctor=user).count(),
            'Certificates Processed': CertificateRequest.objects.filter(processed_by=user).count(),
        }
        recent_activity = {
            'appointments': Appointment.objects.filter(doctor=user).order_by('-created_at')[:5],
            'medical_records': MedicalRecord.objects.filter(doctor=user).order_by('-created_at')[:5],
        }
    else:
        stats = {}
        recent_activity = {}
    
    context = {
        'viewed_user': user,
        'profile': profile,
        'stats': stats,
        'recent_activity': recent_activity,
    }
    
    return render(request, 'core/user_management/user_detail.html', context)


@login_required
@admin_required
def user_create(request):
    """Create a new user"""
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                user = form.save()
                invite_link = ''
                if user.onboarding_status == User.ONBOARDING_STATUS.PENDING_ACTIVATION:
                    _invite, raw_token = _create_user_invite(user=user, created_by=request.user)
                    invite_link = request.build_absolute_uri(
                        reverse('core:accept_invite', kwargs={'token': raw_token})
                    )

                create_action = (
                    AccountProvisioningAudit.ACTION.CREATED_PENDING
                    if user.onboarding_status == User.ONBOARDING_STATUS.PENDING_ACTIVATION
                    else AccountProvisioningAudit.ACTION.CREATED_ACTIVE
                )
                _log_provisioning_action(
                    request=request,
                    actor=request.user,
                    target_user=user,
                    action=create_action,
                    metadata={
                        'onboarding_status': user.onboarding_status,
                        'is_active': user.is_active,
                    },
                )

                # Create notification for the new user
                is_pending_activation = user.onboarding_status == User.ONBOARDING_STATUS.PENDING_ACTIVATION
                create_notification(
                    user=user,
                    title='Welcome to JMCFI Clinic',
                    message=(
                        'Your account has been created. Use your invitation link to activate your account.'
                        if is_pending_activation
                        else 'Your account has been created. Please complete your profile to get started.'
                    ),
                    notification_type='general'
                )

            user_identifier = user.username or user.email
            if user.onboarding_status == User.ONBOARDING_STATUS.PENDING_ACTIVATION:
                messages.success(request, f'User "{user_identifier}" created in pending activation state.')
                if invite_link:
                    messages.info(request, f'Invite link: {invite_link}')
            else:
                messages.success(request, f'User "{user_identifier}" created and activated successfully!')
            return redirect('core:user_detail', user_id=user.id)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = UserCreationForm()
    
    context = {
        'form': form,
        'action': 'Create',
    }
    
    return render(request, 'core/user_management/user_form.html', context)


@login_required
@admin_required
def user_edit(request, user_id):
    """Edit an existing user"""
    user = get_object_or_404(User, id=user_id)
    
    # Prevent editing admin users
    if user.role == 'admin':
        messages.error(request, 'Cannot edit admin users.')
        return redirect('core:user_detail', user_id=user.id)
    
    if request.method == 'POST':
        form = UserEditForm(request.POST, instance=user)
        if form.is_valid():
            old_role = user.role
            user = form.save()
            
            # If role changed, handle profile migration
            if old_role != user.role:
                if old_role == 'student' and user.role == 'staff':
                    # Delete student profile and create staff profile
                    try:
                        user.student_profile.delete()
                    except:
                        pass
                    if not hasattr(user, 'staff_profile'):
                        StaffProfile.objects.create(
                            user=user,
                            staff_id=f'TEMP_{user.id}',
                            phone='',
                            department='Pending'
                        )
                elif old_role == 'staff' and user.role == 'student':
                    # Delete staff profile and create student profile
                    try:
                        user.staff_profile.delete()
                    except:
                        pass
                    if not hasattr(user, 'student_profile'):
                        StudentProfile.objects.create(
                            user=user,
                            student_id=f'TEMP_{user.id}',
                            phone='',
                            emergency_contact='',
                            emergency_phone='',
                            date_of_birth='2000-01-01'
                        )
                
                messages.info(request, f'User role changed from {old_role} to {user.role}. Please update their profile.')
            
            messages.success(request, f'User "{user.username}" updated successfully!')
            return redirect('core:user_detail', user_id=user.id)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = UserEditForm(instance=user)
    
    context = {
        'form': form,
        'action': 'Edit',
        'viewed_user': user,
    }
    
    return render(request, 'core/user_management/user_form.html', context)


@login_required
@admin_required
def user_delete(request, user_id):
    """Delete a user — triggered via unified modal POST from user detail page."""
    user = get_object_or_404(User, id=user_id)
    
    # Prevent deleting admin users
    if user.role == 'admin':
        messages.error(request, 'Cannot delete admin users.')
        return redirect('core:user_detail', user_id=user.id)
    
    # Prevent deleting self
    if user.id == request.user.id:
        messages.error(request, 'Cannot delete your own account.')
        return redirect('core:user_detail', user_id=user.id)
    
    if request.method == 'POST':
        username = user.username
        user.delete()
        messages.success(request, f'User "{username}" has been deleted.')
        return redirect('core:user_management')
    
    # GET requests redirect to user detail page (modal trigger is there)
    return redirect('core:user_detail', user_id=user.id)


@login_required
@admin_required
def user_toggle_status(request, user_id):
    """Toggle user active/inactive status"""
    user = get_object_or_404(User, id=user_id)
    
    # Prevent deactivating admin users
    if user.role == 'admin':
        messages.error(request, 'Cannot deactivate admin users.')
        if request.headers.get('HX-Request') == 'true':
            return render(request, 'partials/messages.html')
        return redirect('core:user_detail', user_id=user.id)
    
    # Prevent deactivating self
    if user.id == request.user.id:
        messages.error(request, 'Cannot deactivate your own account.')
        if request.headers.get('HX-Request') == 'true':
            return render(request, 'partials/messages.html')
        return redirect('core:user_detail', user_id=user.id)
    
    was_pending = user.onboarding_status == User.ONBOARDING_STATUS.PENDING_ACTIVATION
    user.is_active = not user.is_active
    if user.is_active:
        user.onboarding_status = User.ONBOARDING_STATUS.ACTIVE
    else:
        user.onboarding_status = User.ONBOARDING_STATUS.SUSPENDED
    user.save()

    # Get fresh status text for HTMX updating
    if user.onboarding_status == User.ONBOARDING_STATUS.PENDING_ACTIVATION:
        status_html = '''<span class="px-2 py-1 inline-flex text-xs leading-5 font-semibold rounded-full bg-amber-100 text-amber-800">Pending Activation</span>'''
    elif user.is_active:
        status_html = '''<span class="px-2 py-1 inline-flex text-xs leading-5 font-semibold rounded-full bg-green-100 text-green-800"><svg class="w-4 h-4 mr-1" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"></path></svg>Active</span>'''
    else:
        status_html = '''<span class="px-2 py-1 inline-flex text-xs leading-5 font-semibold rounded-full bg-red-100 text-red-800"><svg class="w-4 h-4 mr-1" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M13.477 14.89A6 6 0 015.11 6.524l8.367 8.368zm1.414-1.414L6.524 5.11a6 6 0 018.367 8.367zM18 10a8 8 0 11-16 0 8 8 0 0116 0z" clip-rule="evenodd"></path></svg>Suspended</span>'''

    action = (
        AccountProvisioningAudit.ACTION.ACTIVATED
        if user.is_active
        else AccountProvisioningAudit.ACTION.SUSPENDED
    )
    _log_provisioning_action(
        request=request,
        actor=request.user,
        target_user=user,
        action=action,
        metadata={
            'was_pending': was_pending,
            'onboarding_status': user.onboarding_status,
            'is_active': user.is_active,
        },
    )
    
    if user.is_active:
        status_message = 'Account activated successfully.'
    else:
        status_message = 'Account deactivated successfully.'
    messages.success(request, status_message)
    
    # Create notification for the user
    if user.is_active:
        create_notification(
            user=user,
            title='Account Activated',
            message='Your account has been activated by an administrator.',
            notification_type='general'
        )
    else:
                create_notification(
            user=user,
            title='Account Deactivated',
            message='Your account has been deactivated. Please contact an administrator for more information.',
            notification_type='general'
        )
    
    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.headers.get('HX-Request') == 'true':
        if request.headers.get('x-requested-with') == 'XMLHttpRequest' and not request.headers.get('HX-Request') == 'true':
            messages.get_messages(request).used = True # Clear messages added in this request
            return JsonResponse({
                'status': 'success',
                'is_active': user.is_active,
                'message': status_message,
            })
        else:
            response = render(request, 'partials/messages.html')
            response['HX-Trigger'] = '{"updateStatus": {"id": "' + str(user.id) + '", "html": "' + status_html.replace('"', '\\"') + '"}}'
            return response
    return redirect('core:user_detail', user_id=user.id)


@login_required
@admin_required
def user_resend_invite(request, user_id):
    """Generate a new invite link for a pending user account."""
    user = get_object_or_404(User, id=user_id)

    if user.role == 'admin':
        messages.error(request, 'Cannot manage invites for admin users.')
        return redirect('core:user_detail', user_id=user.id)

    if user.onboarding_status != User.ONBOARDING_STATUS.PENDING_ACTIVATION:
        messages.error(request, 'Invite can only be regenerated for pending activation users.')
        return redirect('core:user_detail', user_id=user.id)

    _invite, raw_token = _create_user_invite(user=user, created_by=request.user)
    invite_link = request.build_absolute_uri(
        reverse('core:accept_invite', kwargs={'token': raw_token})
    )

    create_notification(
        user=user,
        title='New Invitation Link',
        message='A new account invitation link has been generated for you by an administrator.',
        notification_type='general'
    )

    messages.success(request, f'New invite link generated for "{user.email}".')
    messages.info(request, f'Invite link: {invite_link}')
    return redirect('core:user_detail', user_id=user.id)


@login_required
@admin_required
def user_reset_password(request, user_id):
    """Reset user password"""
    user = get_object_or_404(User, id=user_id)
    
    # Prevent resetting admin passwords
    if user.role == 'admin':
        messages.error(request, 'Cannot reset admin user passwords.')
        return redirect('core:user_detail', user_id=user.id)
    
    if request.method == 'POST':
        form = PasswordResetForm(request.POST, user=user)
        if form.is_valid():
            new_password = form.cleaned_data['new_password1']
            user.set_password(new_password)
            user.save()
            
            # Create notification for the user
            create_notification(
                user=user,
                title='Password Reset',
                message='Your password has been reset by an administrator. Please login with your new password.',
                notification_type='general'
            )
            
            messages.success(request, f'Password for "{user.username}" has been reset successfully.')
            return redirect('core:user_detail', user_id=user.id)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = PasswordResetForm(user=user)
    
    context = {
        'form': form,
        'viewed_user': user,
    }
    
    return render(request, 'core/user_management/user_reset_password.html', context)


# =====================
# Search Views
# =====================

@login_required
@role_required('doctor', 'admin')
def search_students(request):
    """
    AJAX endpoint to search for students by name or email.
    Used in forms where a doctor/admin needs to select a student.
    """
    query = request.GET.get('q', '')
    if len(query) < 2:
        return JsonResponse([], safe=False)

    students = User.objects.filter(
        Q(role='student') &
        (Q(first_name__icontains=query) |
         Q(last_name__icontains=query) |
         Q(email__icontains=query))
    )[:10]

    results = [
        {
            'id': student.id,
            'name': student.get_full_name(),
            'email': student.email
        }
        for student in students
    ]
    return JsonResponse(results, safe=False)
