"""Purchase order workflow commands."""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from pharmacy.models import PurchaseOrder
from pharmacy.services.audit import log_action
from pharmacy.services.stock import receive_po_line_item


@transaction.atomic
def create_purchase_order(*, form, formset, user) -> PurchaseOrder:
    po = form.save(commit=False)
    po.ordered_by = user
    po.save()
    formset.instance = po
    formset.save()
    log_action(
        'order_created',
        user,
        details=f'PO {po.order_number} created for {po.supplier.name}.',
    )
    return po


@transaction.atomic
def update_purchase_order(*, order: PurchaseOrder, form, formset, user) -> PurchaseOrder:
    order = PurchaseOrder.objects.select_for_update().get(pk=order.pk)
    if order.status != 'draft':
        raise ValueError('Only draft purchase orders can be edited.')
    po = form.save(commit=False)
    po.pk = order.pk
    po.ordered_by = order.ordered_by
    po.status = order.status
    po.order_number = order.order_number
    po.save()
    formset.instance = po
    formset.save()
    log_action(
        'order_created',
        user,
        details=f'PO {po.order_number} updated.',
    )
    return po


@transaction.atomic
def submit_purchase_order(order: PurchaseOrder, user) -> bool:
    order = PurchaseOrder.objects.select_for_update().get(pk=order.pk)
    if order.status != 'draft':
        return False
    if not order.items.exists():
        return False
    order.status = 'submitted'
    order.save(update_fields=['status', 'updated_at'])
    log_action(
        'order_created',
        user,
        details=f'PO {order.order_number} submitted for approval.',
    )
    return True


@transaction.atomic
def approve_purchase_order(order: PurchaseOrder, user) -> bool:
    order = PurchaseOrder.objects.select_for_update().get(pk=order.pk)
    if order.status not in ('draft', 'submitted'):
        return False
    order.status = 'approved'
    order.approved_by = user
    order.save(update_fields=['status', 'approved_by', 'updated_at'])
    log_action(
        'order_approved',
        user,
        details=f'PO {order.order_number} approved.',
    )
    return True


@transaction.atomic
def receive_purchase_order(order: PurchaseOrder, user) -> bool:
    order = PurchaseOrder.objects.select_for_update().get(pk=order.pk)
    if order.status != 'approved':
        return False

    for item in order.items.select_related('medicine').all():
        receive_po_line_item(order, item, user)

    order.status = 'received'
    order.received_date = timezone.now().date()
    order.save(update_fields=['status', 'received_date', 'updated_at'])
    log_action(
        'order_received',
        user,
        details=f'PO {order.order_number} fully received.',
    )
    return True
