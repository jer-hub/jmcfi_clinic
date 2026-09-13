"""Notification views."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from core.decorators import admin_required
from core.forms import SystemNotificationForm
from core.htmx_utils import htmx_redirect, is_htmx_request
from core.models import Notification
from core.notification_delivery import (
    deliver_bulk_notifications,
    resolve_system_notification_recipients,
)
from core.utils import resolve_notification_url, user_visible_notifications


@login_required
def notifications(request):
    """Display user notifications"""
    base_qs = user_visible_notifications(request.user)
    notifications_qs = base_qs.order_by('-created_at')

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
        base_qs.filter(is_read=False).update(is_read=True)
        messages.success(request, 'All notifications marked as read.')
        return redirect('core:notifications')

    paginator = Paginator(notifications_qs, 15)
    page = request.GET.get('page')
    notifications_page = paginator.get_page(page)

    # Get counts for filters
    total_count = base_qs.count()
    unread_count = base_qs.filter(is_read=False).count()
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
@require_http_methods(['GET', 'POST'])
def mark_notification_read(request, notification_id):
    """Mark notification read (if needed) and redirect to its target page."""
    notification = get_object_or_404(Notification, id=notification_id, user=request.user)
    if not notification.is_read:
        notification.is_read = True
        notification.save(update_fields=['is_read'])

    target = resolve_notification_url(notification) or reverse('core:notifications')
    if is_htmx_request(request):
        return htmx_redirect(target)
    return redirect(target)


@login_required
def mark_all_notifications_read(request):
    """Mark all notifications as read for the current user"""
    if request.method == 'POST':
        updated_count = user_visible_notifications(request.user).filter(
            is_read=False,
        ).update(is_read=True)
        return JsonResponse({
            'status': 'success', 
            'message': f'{updated_count} notifications marked as read'
        })
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'})


@login_required
@require_http_methods(['POST'])
def clear_all_notifications(request):
    """Delete all notifications for the current user"""
    notifications_qs = user_visible_notifications(request.user)
    if notifications_qs.exists():
        notifications_qs.delete()
        messages.success(request, 'All notifications cleared.')
    else:
        messages.info(request, 'No notifications to clear.')
    return redirect('core:notifications')


@login_required
@admin_required
def create_system_notification(request):
    """Allow admins to create system-wide notifications."""
    if request.method == 'POST':
        form = SystemNotificationForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            recipients = resolve_system_notification_recipients(data['recipient_type'])
            deliver_bulk_notifications(
                recipients,
                data['title'],
                data['message'],
                data['notification_type'],
            )
            messages.success(request, 'Notification sent successfully.')
            return redirect('core:notifications')
    else:
        form = SystemNotificationForm()

    return render(
        request,
        'core/create_system_notification.html',
        {'form': form},
    )
