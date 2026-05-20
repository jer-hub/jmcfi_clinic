"""Cached medicine stock snapshots for list/dashboard performance."""

from __future__ import annotations

from datetime import date

from django.db.models import Q, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from pharmacy.models import Batch, Medicine


def compute_non_expired_stock(medicine_id: int, today: date | None = None) -> int:
    today = today or timezone.now().date()
    total = Batch.objects.filter(
        medicine_id=medicine_id,
        quantity__gt=0,
        expiry_date__gt=today,
    ).aggregate(
        total=Coalesce(Sum('quantity'), 0),
    )['total']
    return int(total or 0)


def refresh_medicine_stock_cache(medicine_id: int, today: date | None = None) -> Medicine:
    """Recompute and persist cached_non_expired_stock for one medicine."""
    today = today or timezone.now().date()
    qty = compute_non_expired_stock(medicine_id, today)
    Medicine.objects.filter(pk=medicine_id).update(
        cached_non_expired_stock=qty,
        stock_cache_updated_at=timezone.now(),
    )
    return Medicine.objects.get(pk=medicine_id)


def refresh_all_medicine_stock_caches(*, active_only: bool = True) -> int:
    """Backfill or repair all medicine stock caches. Returns rows updated."""
    qs = Medicine.objects.all()
    if active_only:
        qs = qs.filter(is_active=True)
    count = 0
    today = timezone.now().date()
    for med_id in qs.values_list('pk', flat=True):
        refresh_medicine_stock_cache(med_id, today)
        count += 1
    return count
