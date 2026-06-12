"""Inventory stock calculations and movements."""

from __future__ import annotations

from datetime import date, timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F, Q, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from core.notification_delivery import notify_user

from pharmacy.models import Batch, Dispensing, Medicine, StockAdjustment
from pharmacy.services.audit import log_action


def active_medicines_queryset(today: date | None = None):
    """Active medicines annotated with non-expired batch quantity."""
    today = today or timezone.now().date()
    return Medicine.objects.filter(is_active=True).annotate(
        non_expired_stock=Coalesce(
            Sum(
                'batches__quantity',
                filter=Q(batches__quantity__gt=0, batches__expiry_date__gt=today),
            ),
            0,
        )
    )


def low_stock_medicines(today: date | None = None, *, limit: int = 10):
    qs = Medicine.objects.filter(
        is_active=True,
        cached_non_expired_stock__lte=F('reorder_level'),
    ).order_by('cached_non_expired_stock', 'name')
    items = list(qs[:limit])
    for med in items:
        med.display_stock = med.cached_non_expired_stock
        med.non_expired_stock = med.cached_non_expired_stock
    return qs, items


def overstocked_medicines(today: date | None = None, *, limit: int = 10):
    qs = Medicine.objects.filter(
        is_active=True,
        cached_non_expired_stock__gt=F('max_stock_level'),
    ).order_by('-cached_non_expired_stock', 'name')
    items = list(qs[:limit])
    for med in items:
        med.non_expired_stock = med.cached_non_expired_stock
    return qs, items


def near_expiry_batches(today: date | None = None, *, days: int = 90):
    today = today or timezone.now().date()
    cutoff = today + timedelta(days=days)
    qs = Batch.objects.filter(
        quantity__gt=0,
        expiry_date__gt=today,
        expiry_date__lte=cutoff,
    ).select_related('medicine')
    return qs, list(qs[:10])


def expired_batches(today: date | None = None, *, limit: int = 10):
    today = today or timezone.now().date()
    qs = Batch.objects.filter(
        quantity__gt=0,
        expiry_date__lte=today,
    ).select_related('medicine')
    return qs, list(qs[:limit])


def log_medicine_added(medicine, user) -> None:
    log_action(
        'medicine_added',
        user,
        medicine=medicine,
        details=f'Medicine "{medicine.name}" added to catalog by {user}.',
    )


def create_opening_stock(medicine, cleaned_data: dict, user) -> Batch | None:
    """Create opening batch from MedicineForm cleaned_data; returns batch or None."""
    opening_qty = cleaned_data.get('opening_quantity')
    if not opening_qty:
        return None

    batch = Batch.objects.create(
        medicine=medicine,
        batch_number=cleaned_data['opening_batch_number'],
        quantity=opening_qty,
        unit_cost=cleaned_data.get('opening_unit_cost') or 0,
        expiry_date=cleaned_data['opening_expiry_date'],
        received_date=timezone.now().date(),
        notes='Opening stock added during medicine creation.',
    )
    log_action(
        'stock_in',
        user,
        medicine=medicine,
        batch=batch,
        quantity=opening_qty,
        details=(
            f'Opening stock of {opening_qty} unit(s) added for '
            f'"{medicine.name}" (Batch {batch.batch_number}).'
        ),
    )
    return batch


def log_batch_stock_in(batch: Batch, user, *, details: str | None = None) -> None:
    log_action(
        'stock_in',
        user,
        medicine=batch.medicine,
        batch=batch,
        quantity=batch.quantity,
        details=details or f'New batch {batch.batch_number} added with {batch.quantity} units.',
    )


def log_batch_quantity_edit(batch: Batch, user, old_qty: int) -> None:
    if batch.quantity == old_qty:
        return
    log_action(
        'adjustment',
        user,
        medicine=batch.medicine,
        batch=batch,
        quantity=batch.quantity - old_qty,
        details=f'Batch {batch.batch_number} edited. Qty {old_qty}→{batch.quantity}.',
    )


def receive_po_line_item(order, item, user) -> Batch:
    """Create or increment batch from a received purchase order line."""
    batch, created = Batch.objects.get_or_create(
        medicine=item.medicine,
        batch_number=f'PO-{order.order_number}-{item.pk}',
        defaults={
            'quantity': item.quantity_ordered,
            'unit_cost': item.unit_cost,
            'expiry_date': timezone.now().date() + timedelta(days=730),
            'received_date': timezone.now().date(),
        },
    )
    if not created:
        batch.quantity += item.quantity_ordered
        batch.save(update_fields=['quantity', 'updated_at'])

    item.quantity_received = item.quantity_ordered
    item.save(update_fields=['quantity_received'])

    log_action(
        'stock_in',
        user,
        medicine=item.medicine,
        batch=batch,
        quantity=item.quantity_ordered,
        details=f'Received {item.quantity_ordered} units from PO {order.order_number}.',
    )
    return batch


@transaction.atomic
def dispense_and_deduct(dispensing: Dispensing, user) -> None:
    """Persist dispensing, deduct batch stock, audit, and notify patient."""
    batch = Batch.objects.select_for_update().get(pk=dispensing.batch_id)
    if batch.quantity < dispensing.quantity:
        raise ValidationError(
            f'Insufficient stock in batch {batch.batch_number}: '
            f'{batch.quantity} available, {dispensing.quantity} requested.'
        )

    dispensing.batch = batch
    dispensing.dispensed_by = user
    dispensing.save()

    batch.quantity -= dispensing.quantity
    batch.save(update_fields=['quantity', 'updated_at'])

    log_action(
        'dispensed',
        user,
        medicine=batch.medicine,
        batch=batch,
        quantity=dispensing.quantity,
        details=(
            f'Dispensed {dispensing.quantity} {batch.medicine.unit} of {batch.medicine.name} '
            f'to {dispensing.patient.first_name} {dispensing.patient.last_name}.'
        ),
    )

    notify_user(
        dispensing.patient,
        title='Medicine Dispensed',
        message=(
            f'{dispensing.quantity} {batch.medicine.unit}(s) of {batch.medicine.name} '
            f'has been dispensed to you.'
        ),
        notification_type='general',
        transaction_type='general_announcement',
    )


@transaction.atomic
def apply_stock_adjustment(adjustment: StockAdjustment, user) -> None:
    """Save adjustment, update batch quantity, and write audit entry."""
    batch = Batch.objects.select_for_update().get(pk=adjustment.batch_id)
    new_qty = batch.quantity + adjustment.quantity_change
    if new_qty < 0:
        raise ValidationError(
            f'Adjustment would make batch {batch.batch_number} negative '
            f'({batch.quantity} on hand, change {adjustment.quantity_change:+d}).'
        )

    adjustment.batch = batch
    adjustment.adjusted_by = user
    adjustment.save()

    batch.quantity = new_qty
    batch.save(update_fields=['quantity', 'updated_at'])

    action = 'expired_disposed' if adjustment.reason == 'expired' else 'adjustment'
    log_action(
        action,
        user,
        medicine=batch.medicine,
        batch=batch,
        quantity=adjustment.quantity_change,
        details=(
            f'Stock adjustment ({adjustment.get_reason_display()}): '
            f'{adjustment.quantity_change:+d} on {batch.medicine.name} '
            f'Batch {batch.batch_number}.'
        ),
    )


def medicine_detail_payload(medicine) -> dict:
    """JSON-serializable medicine metadata for dispensing form."""
    return {
        'id': medicine.pk,
        'name': str(medicine),
        'unit': medicine.unit,
        'unit_display': medicine.get_unit_display(),
        'strength': medicine.strength or '',
        'requires_prescription': medicine.requires_prescription,
        'current_stock': medicine.current_stock,
    }


def available_batches_payload(medicine_id: int) -> list[dict]:
    """JSON-serializable batches for dispensing form API."""
    today = timezone.now().date()
    batches = Batch.objects.filter(
        medicine_id=medicine_id,
        quantity__gt=0,
        expiry_date__gt=today,
    ).order_by('expiry_date')
    return [
        {
            'id': b.id,
            'batch_number': b.batch_number,
            'quantity': b.quantity,
            'expiry_date': b.expiry_date.isoformat(),
            'unit_cost': str(b.unit_cost),
        }
        for b in batches
    ]
