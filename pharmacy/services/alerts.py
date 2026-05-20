"""Scheduled inventory alerts for pharmacy staff."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db.models import F
from django.utils import timezone

from core.notification_delivery import notify_user

from pharmacy.models import Medicine
from pharmacy.services.stock import expired_batches, near_expiry_batches

User = get_user_model()


def staff_recipients():
    return User.objects.filter(role='staff', is_active=True)


def run_inventory_alerts(*, near_expiry_days: int = 90, dry_run: bool = False) -> dict:
    """
    Notify all active staff about low stock, near-expiry, and expired batches.

    Returns counts of notifications that would be or were sent (one per staff per category).
    """
    today = timezone.now().date()
    low_count = Medicine.objects.filter(
        is_active=True,
        cached_non_expired_stock__lte=F('reorder_level'),
    ).count()
    near_expiry_qs, _ = near_expiry_batches(today, days=near_expiry_days)
    near_count = near_expiry_qs.count()
    expired_qs, _ = expired_batches(today, limit=500)
    expired_count = expired_qs.count()

    stats = {
        'low_stock_medicines': low_count,
        'near_expiry_batches': near_count,
        'expired_batches': expired_count,
        'notifications_sent': 0,
        'dry_run': dry_run,
    }

    recipients = list(staff_recipients())
    if not recipients:
        return stats

    alerts = []
    if low_count:
        alerts.append((
            'Pharmacy: Low Stock',
            f'{low_count} medicine(s) are at or below reorder level. Review the pharmacy dashboard.',
        ))
    if near_count:
        alerts.append((
            'Pharmacy: Near Expiry',
            f'{near_count} batch(es) expire within {near_expiry_days} days. Check batch inventory.',
        ))
    if expired_count:
        alerts.append((
            'Pharmacy: Expired Stock',
            f'{expired_count} batch(es) have expired but still show quantity on hand. Dispose or adjust stock.',
        ))

    for title, message in alerts:
        for user in recipients:
            if dry_run:
                continue
            notify_user(
                user,
                title=title,
                message=message,
                notification_type='general',
                transaction_type='general_announcement',
            )
            stats['notifications_sent'] += 1

    return stats
