"""Atomic purchase order number allocation."""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from pharmacy.models import PharmacyCounter


def allocate_purchase_order_number() -> str:
    """Next unique PO number: YYYYMM-#### (sequence is monotonic under concurrency)."""
    prefix = timezone.now().strftime('%Y%m')
    with transaction.atomic():
        PharmacyCounter.objects.get_or_create(
            pk=1,
            defaults={'next_purchase_order_seq': 0},
        )
        counter = PharmacyCounter.objects.select_for_update().get(pk=1)
        counter.next_purchase_order_seq += 1
        counter.save(update_fields=['next_purchase_order_seq'])
        seq = counter.next_purchase_order_seq
    return f'{prefix}-{seq:04d}'
