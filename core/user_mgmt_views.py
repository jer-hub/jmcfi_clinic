"""
Extended user management views for bulk operations, export, and audit trails.

These views are separated from core/views.py to keep the main views file manageable.
They are imported and registered in core/urls.py.
"""
import csv
import logging

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone

from .decorators import admin_required
from .user_management_services import restore_user
from .forms import BulkUserActionForm, UserExportForm
from .models import (
    AccountProvisioningAudit,
    Notification,
    User,
)
from .utils import (
    create_notification,
    get_user_profile,
    paginate_queryset,
)

auth_logger = logging.getLogger('security.auth')
User = User  # Use the global User model


@login_required
@admin_required
def user_bulk_action(request):
    """
    Handle bulk operations on users: activate, deactivate, soft-delete.
    Accepts POST with user_ids (comma-separated) and action type.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'POST required.'}, status=405)

    form = BulkUserActionForm(request.POST)
    if not form.is_valid():
        return JsonResponse({'status': 'error', 'message': 'Invalid form data.', 'errors': form.errors}, status=400)

    action = form.cleaned_data['action']
    user_ids = form.cleaned_data['user_ids']

    users = User.objects.filter(id__in=user_ids)

    # Prevent operating on admin users
    admin_ids = list(users.filter(role='admin').values_list('id', flat=True))
    if admin_ids:
        users = users.exclude(role='admin')

    if not users.exists():
        return JsonResponse({'status': 'error', 'message': 'No valid (non-admin) users found.'}, status=400)

    if action == 'activate':
        updated = users.update(
            is_active=True,
            onboarding_status='active',
        )
        for user in users:
            create_notification(
                user=user,
                title='Account Activated',
                message='Your account has been activated by an administrator (bulk action).',
                notification_type='general',
            )
            _log_audit(request, user, AccountProvisioningAudit.ACTION.BULK_ACTIVATED)
        msg = f'{updated} user(s) activated successfully.'
        if admin_ids:
            msg += f' {len(admin_ids)} admin user(s) skipped.'

    elif action == 'deactivate':
        # Don't deactivate the requesting admin
        users = users.exclude(id=request.user.id)
        updated = users.update(
            is_active=False,
            onboarding_status='suspended',
        )
        for user in users:
            create_notification(
                user=user,
                title='Account Deactivated',
                message='Your account has been deactivated by an administrator (bulk action).',
                notification_type='general',
            )
            _log_audit(request, user, AccountProvisioningAudit.ACTION.BULK_SUSPENDED)
        msg = f'{updated} user(s) deactivated successfully.'
        if admin_ids:
            msg += f' {len(admin_ids)} admin user(s) skipped.'

    elif action == 'delete':
        users = users.exclude(id=request.user.id)
        updated = 0
        for user in users:
            user.soft_delete()
            create_notification(
                user=user,
                title='Account Deleted',
                message='Your account has been deleted by an administrator. Please contact support.',
                notification_type='general',
            )
            _log_audit(request, user, AccountProvisioningAudit.ACTION.SOFT_DELETED)
            updated += 1
        msg = f'{updated} user(s) soft-deleted successfully.'
        if admin_ids:
            msg += f' {len(admin_ids)} admin user(s) skipped.'

    else:
        return JsonResponse({'status': 'error', 'message': 'Unknown action.'}, status=400)

    return JsonResponse({'status': 'success', 'message': msg})


@login_required
@admin_required
def user_restore(request, user_id):
    """Restore a soft-deleted user."""
    user = get_object_or_404(User, id=user_id, is_deleted=True)

    restore_user(request=request, actor=request.user, target_user=user)
    create_notification(
        user=user,
        title='Account Restored',
        message='Your account has been restored by an administrator.',
        notification_type='general',
    )
    _log_audit(request, user, AccountProvisioningAudit.ACTION.RESTORED)
    messages.success(request, f'User "{user.email}" has been restored successfully.')
    return redirect('core:user_detail', user_id=user.id)


@login_required
@admin_required
def user_audit_log(request, user_id):
    """View the audit trail for a specific user."""
    user = get_object_or_404(User, id=user_id)
    audits = AccountProvisioningAudit.objects.filter(target_user=user).select_related('actor')

    # Apply date filters
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    action_filter = request.GET.get('action', '')

    if date_from:
        audits = audits.filter(created_at__date__gte=date_from)
    if date_to:
        audits = audits.filter(created_at__date__lte=date_to)
    if action_filter:
        audits = audits.filter(action=action_filter)

    audits = audits.order_by('-created_at')
    audits_page = paginate_queryset(audits, request, per_page=20)

    context = {
        'viewed_user': user,
        'audits': audits_page,
        'action_filter': action_filter,
        'date_from': date_from,
        'date_to': date_to,
        'action_choices': AccountProvisioningAudit.ACTION.choices,
    }
    return render(request, 'core/user_management/user_audit_log.html', context)


@login_required
@admin_required
def user_export_csv(request):
    """Export users list as CSV file with optional filters."""
    form = UserExportForm(request.GET or None)

    users = User.objects.all().order_by('-date_joined')

    if form.is_valid():
        role = form.cleaned_data.get('role')
        status = form.cleaned_data.get('status')
        date_from = form.cleaned_data.get('date_from')
        date_to = form.cleaned_data.get('date_to')

        if role:
            users = users.filter(role=role)
        if status == 'active':
            users = users.filter(is_active=True, onboarding_status='active')
        elif status == 'pending':
            users = users.filter(onboarding_status='pending_activation')
        elif status == 'suspended':
            users = users.filter(onboarding_status='suspended')
        if date_from:
            users = users.filter(date_joined__date__gte=date_from)
        if date_to:
            users = users.filter(date_joined__date__lte=date_to)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="jmcfi_users_export.csv"'

    writer = csv.writer(response)
    writer.writerow([
        'ID', 'Email', 'Username', 'First Name', 'Last Name',
        'Role', 'Status', 'Is Active', 'Is Deleted',
        'Date Joined', 'Last Login', 'Last Activity',
        'Profile ID', 'Profile Phone', 'Profile Department',
    ])

    for user in users.select_related().iterator():
        profile = get_user_profile(user)
        profile_id = ''
        profile_phone = ''
        profile_dept = ''

        if profile:
            profile_id = getattr(profile, 'student_id', '') or getattr(profile, 'staff_id', '')
            profile_phone = getattr(profile, 'phone', '')
            profile_dept = getattr(profile, 'department', '')

        writer.writerow([
            user.id, user.email, user.username or '', user.first_name, user.last_name,
            user.role, user.onboarding_status, user.is_active, user.is_deleted,
            user.date_joined.strftime('%Y-%m-%d %H:%M:%S') if user.date_joined else '',
            user.last_login.strftime('%Y-%m-%d %H:%M:%S') if user.last_login else '',
            user.last_activity_at.strftime('%Y-%m-%d %H:%M:%S') if user.last_activity_at else '',
            profile_id, profile_phone or '', profile_dept or '',
        ])

    return response


@login_required
@admin_required
def user_cleanup_stale(request):
    """
    Admin view to find and optionally deactivate stale users
    (pending activation for too long, no activity for months).
    """
    now = timezone.now()

    # Users pending activation for more than 30 days
    stale_pending = User.objects.filter(
        onboarding_status='pending_activation',
        date_joined__lte=now - timezone.timedelta(days=30),
        is_deleted=False,
    )

    # Users with no activity for more than 6 months
    stale_inactive = User.objects.filter(
        is_active=True,
        is_deleted=False,
        last_activity_at__lte=now - timezone.timedelta(days=180),
    ).exclude(role='admin')

    # Users with no last_activity_at and joined more than 6 months ago
    stale_no_activity = User.objects.filter(
        is_active=True,
        is_deleted=False,
        last_activity_at__isnull=True,
        date_joined__lte=now - timezone.timedelta(days=180),
    ).exclude(role='admin')

    if request.method == 'POST' and request.POST.get('action') == 'deactivate_stale':
        target_users = User.objects.none()

        if request.POST.get('deactivate_pending'):
            target_users = target_users | stale_pending
        if request.POST.get('deactivate_inactive'):
            target_users = target_users | stale_inactive
        if request.POST.get('deactivate_no_activity'):
            target_users = target_users | stale_no_activity

        target_users = target_users.distinct().exclude(id=request.user.id)
        count = 0
        for user in target_users:
            user.is_active = False
            user.onboarding_status = User.ONBOARDING_STATUS.SUSPENDED
            user.save(update_fields=['is_active', 'onboarding_status'])
            _log_audit(request, user, AccountProvisioningAudit.ACTION.SUSPENDED)
            count += 1

        messages.success(request, f'{count} stale user(s) have been deactivated.')
        return redirect('core:user_cleanup_stale')

    context = {
        'stale_pending': stale_pending[:20],
        'stale_pending_count': stale_pending.count(),
        'stale_inactive': stale_inactive[:20],
        'stale_inactive_count': stale_inactive.count(),
        'stale_no_activity': stale_no_activity[:20],
        'stale_no_activity_count': stale_no_activity.count(),
    }
    return render(request, 'core/user_management/user_cleanup_stale.html', context)


def _log_audit(request, target_user, action):
    """Helper to log provisioning audit entries."""
    from .models import AccountProvisioningAudit
    from core.views import _get_client_ip

    AccountProvisioningAudit.objects.create(
        actor=request.user,
        target_user=target_user,
        action=action,
        ip_address=_get_client_ip(request),
        metadata={
            'triggered_by': 'bulk_action' if 'bulk' in action else 'single_action',
        },
    )
