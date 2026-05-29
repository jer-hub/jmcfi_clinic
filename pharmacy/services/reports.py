"""Pharmacy reporting and dashboard aggregations."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.db.models import Count, DecimalField, F, Q, Sum
from django.db.models.functions import Coalesce, TruncMonth
from django.utils import timezone

from pharmacy.models import Batch, Dispensing, Medicine, PurchaseOrder, PurchaseOrderItem
from pharmacy.services.stock import (
    expired_batches as get_expired_batches,
    low_stock_medicines as get_low_stock_medicines,
    near_expiry_batches as get_near_expiry_batches,
    overstocked_medicines as get_overstocked_medicines,
)

DECIMAL_OUTPUT = DecimalField(max_digits=12, decimal_places=2)


def current_month_start(today: date | None = None) -> date:
    today = today or timezone.now().date()
    return today.replace(day=1)


def current_year_start(today: date | None = None) -> date:
    today = today or timezone.now().date()
    return today.replace(month=1, day=1)


def dispensing_totals_since(start_date: date) -> dict:
    return Dispensing.objects.filter(dispensed_at__date__gte=start_date).aggregate(
        total_qty=Coalesce(Sum('quantity'), 0),
        total_cost=Coalesce(
            Sum(F('quantity') * F('batch__unit_cost'), output_field=DECIMAL_OUTPUT),
            Decimal('0.00'),
        ),
    )


def procurement_totals_since(start_date: date) -> dict:
    return PurchaseOrderItem.objects.filter(
        purchase_order__status='received',
        purchase_order__received_date__gte=start_date,
    ).aggregate(
        total_qty=Coalesce(Sum('quantity_ordered'), 0),
        total_cost=Coalesce(
            Sum(F('quantity_ordered') * F('unit_cost'), output_field=DECIMAL_OUTPUT),
            Decimal('0.00'),
        ),
    )


def build_dashboard_context(today: date | None = None) -> dict:
    today = today or timezone.now().date()
    month_start = current_month_start(today)

    low_stock_qs, low_stock_medicines = get_low_stock_medicines(today)
    _, overstocked_medicines = get_overstocked_medicines(today)
    near_expiry_qs, near_expiry_batches = get_near_expiry_batches(today)
    expired_qs, expired_batches = get_expired_batches(today)

    return {
        'total_medicines': Medicine.objects.filter(is_active=True).count(),
        'low_stock_medicines': low_stock_medicines,
        'low_stock_count': low_stock_qs.count(),
        'overstocked_medicines': overstocked_medicines,
        'near_expiry_batches': near_expiry_batches,
        'near_expiry_count': near_expiry_qs.count(),
        'expired_batches': expired_batches,
        'expired_count': expired_qs.count(),
        'recent_dispensings': Dispensing.objects.select_related(
            'patient', 'dispensed_by', 'batch__medicine',
        )[:5],
        'pending_orders': PurchaseOrder.objects.filter(
            status__in=['draft', 'submitted', 'approved'],
        ).select_related('supplier')[:5],
        'monthly_dispensed_cost': dispensing_totals_since(month_start)['total_cost'],
        'monthly_procurement_cost': procurement_totals_since(month_start)['total_cost'],
    }


def inventory_value_total() -> Decimal:
    return Batch.objects.filter(quantity__gt=0).aggregate(
        total=Coalesce(
            Sum(F('quantity') * F('unit_cost'), output_field=DECIMAL_OUTPUT),
            Decimal('0.00'),
        )
    )['total']


def build_compliance_context(today: date | None = None) -> dict:
    today = today or timezone.now().date()
    month_start = current_month_start(today)
    year_start = current_year_start(today)

    expired_inventory = Batch.objects.filter(
        quantity__gt=0,
        expiry_date__lte=today,
    ).select_related('medicine').aggregate(
        count=Count('id'),
        total_qty=Coalesce(Sum('quantity'), 0),
        total_value=Coalesce(
            Sum(F('quantity') * F('unit_cost'), output_field=DECIMAL_OUTPUT),
            Decimal('0.00'),
        ),
    )

    top_dispensed = (
        Dispensing.objects.filter(dispensed_at__date__gte=year_start)
        .values('batch__medicine__name')
        .annotate(total_qty=Sum('quantity'))
        .order_by('-total_qty')[:10]
    )

    return {
        'today': today,
        'monthly_dispensed': dispensing_totals_since(month_start),
        'monthly_procured': procurement_totals_since(month_start),
        'yearly_dispensed': dispensing_totals_since(year_start),
        'yearly_procured': procurement_totals_since(year_start),
        'expired_inventory': expired_inventory,
        'top_dispensed': top_dispensed,
    }


def build_cost_analysis_context(today: date | None = None) -> dict:
    today = today or timezone.now().date()
    month_start = current_month_start(today)
    year_start = current_year_start(today)

    supplier_costs = (
        PurchaseOrderItem.objects.filter(
            purchase_order__status='received',
            purchase_order__received_date__gte=month_start,
        )
        .values('purchase_order__supplier__name')
        .annotate(
            total_cost=Sum(F('quantity_ordered') * F('unit_cost'), output_field=DECIMAL_OUTPUT),
            total_items=Sum('quantity_ordered'),
        )
        .order_by('-total_cost')
    )

    medicine_costs = (
        Batch.objects.filter(quantity__gt=0)
        .values('medicine__name')
        .annotate(
            stock_value=Sum(F('quantity') * F('unit_cost'), output_field=DECIMAL_OUTPUT),
            total_qty=Sum('quantity'),
        )
        .order_by('-stock_value')[:15]
    )

    monthly_trend = (
        PurchaseOrderItem.objects.filter(
            purchase_order__status='received',
            purchase_order__received_date__gte=year_start,
        )
        .annotate(month=TruncMonth('purchase_order__received_date'))
        .values('month')
        .annotate(
            total=Sum(F('quantity_ordered') * F('unit_cost'), output_field=DECIMAL_OUTPUT),
        )
        .order_by('month')
    )

    return {
        'inventory_value': inventory_value_total(),
        'supplier_costs': supplier_costs,
        'medicine_costs': medicine_costs,
        'monthly_trend': list(monthly_trend),
    }


def build_pharmacy_analytics_summary(date_from: date, date_to: date) -> dict:
    """Cross-app analytics payload; reuses pharmacy report services."""
    today = timezone.now().date()
    month_start = current_month_start(today)
    low_stock_qs, _ = get_low_stock_medicines(today, limit=5)
    near_expiry_qs, near_expiry_batches = get_near_expiry_batches(today)
    dispensed = dispensing_totals_since(date_from)
    procured = procurement_totals_since(date_from)

    pending_orders = PurchaseOrder.objects.filter(
        status__in=['draft', 'submitted', 'approved'],
    ).count()
    dispensed_cost = dispensed['total_cost']
    procured_cost = procured['total_cost']

    return {
        'active_medicines': Medicine.objects.filter(is_active=True).count(),
        'low_stock_count': low_stock_qs.count(),
        'near_expiry_count': near_expiry_qs.count(),
        'expired_count': get_expired_batches(today)[0].count(),
        'inventory_value': inventory_value_total(),
        'pending_orders': pending_orders,
        'period_dispensed_qty': dispensed['total_qty'],
        'period_dispensed_cost': dispensed_cost,
        'period_procured_cost': procured_cost,
        'dispensed_hint': f'₱{dispensed_cost:,.2f} cost in selected period',
        'procured_hint': (
            f'₱{procured_cost:,.2f} received · {pending_orders} pending PO(s)'
        ),
        'monthly_dispensed_cost': dispensing_totals_since(month_start)['total_cost'],
        'monthly_procured_cost': procurement_totals_since(month_start)['total_cost'],
        'low_stock_preview': list(low_stock_qs[:5]),
        'near_expiry_preview': near_expiry_batches,
    }
