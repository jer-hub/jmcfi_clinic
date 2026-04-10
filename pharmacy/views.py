from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db import transaction
from django.db.models import Q, Sum, F, Count, DecimalField
from django.db.models.functions import Coalesce
from django.utils import timezone
from decimal import Decimal

from core.decorators import role_required
from core.utils import paginate_queryset
from core.models import Notification

from .models import (
    Medicine, MedicineCategory, Batch, Supplier,
    PurchaseOrder, PurchaseOrderItem, Dispensing,
    StockAdjustment, AuditLog,
)
from .forms import (
    MedicineForm, MedicineCategoryForm, BatchForm, SupplierForm,
    PurchaseOrderForm, PurchaseOrderItemFormSet, DispensingForm,
    StockAdjustmentForm,
)


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _log(action, user, medicine=None, batch=None, quantity=0, details=''):
    AuditLog.objects.create(
        action=action, performed_by=user,
        medicine=medicine, batch=batch,
        quantity=quantity, details=details,
    )


# ─── Dashboard ───────────────────────────────────────────────────────────────

@login_required
@role_required('admin', 'staff')
def pharmacy_dashboard(request):
    """Pharmacy overview with KPIs and alerts."""
    today = timezone.now().date()
    ninety_days = today + timezone.timedelta(days=90)

    total_medicines = Medicine.objects.filter(is_active=True).count()

    # Low-stock medicines
    low_stock_medicines = []
    overstocked_medicines = []
    for med in Medicine.objects.filter(is_active=True).prefetch_related('batches'):
        if med.is_low_stock:
            low_stock_medicines.append(med)
        if med.is_overstocked:
            overstocked_medicines.append(med)

    # Expiry alerts
    near_expiry_batches = Batch.objects.filter(
        quantity__gt=0, expiry_date__gt=today, expiry_date__lte=ninety_days,
    ).select_related('medicine')[:10]

    expired_batches = Batch.objects.filter(
        quantity__gt=0, expiry_date__lte=today,
    ).select_related('medicine')[:10]

    # Recent dispensings
    recent_dispensings = Dispensing.objects.select_related(
        'patient', 'dispensed_by', 'batch__medicine'
    )[:5]

    # Pending purchase orders
    pending_orders = PurchaseOrder.objects.filter(
        status__in=['draft', 'submitted', 'approved']
    ).select_related('supplier')[:5]

    # Cost summary (current month)
    month_start = today.replace(day=1)
    monthly_dispensed_cost = Dispensing.objects.filter(
        dispensed_at__date__gte=month_start,
    ).aggregate(
        total=Coalesce(Sum(F('quantity') * F('batch__unit_cost'), output_field=DecimalField()), Decimal('0.00'))
    )['total']

    monthly_procurement_cost = PurchaseOrderItem.objects.filter(
        purchase_order__status='received',
        purchase_order__received_date__gte=month_start,
    ).aggregate(
        total=Coalesce(Sum(F('quantity_ordered') * F('unit_cost'), output_field=DecimalField()), Decimal('0.00'))
    )['total']

    context = {
        'total_medicines': total_medicines,
        'low_stock_medicines': low_stock_medicines,
        'low_stock_count': len(low_stock_medicines),
        'overstocked_medicines': overstocked_medicines,
        'near_expiry_batches': near_expiry_batches,
        'near_expiry_count': Batch.objects.filter(
            quantity__gt=0, expiry_date__gt=today, expiry_date__lte=ninety_days
        ).count(),
        'expired_batches': expired_batches,
        'expired_count': Batch.objects.filter(quantity__gt=0, expiry_date__lte=today).count(),
        'recent_dispensings': recent_dispensings,
        'pending_orders': pending_orders,
        'monthly_dispensed_cost': monthly_dispensed_cost,
        'monthly_procurement_cost': monthly_procurement_cost,
    }
    return render(request, 'pharmacy/dashboard.html', context)


# ─── Medicine CRUD ───────────────────────────────────────────────────────────

@login_required
@role_required('admin', 'staff')
def medicine_list(request):
    qs = Medicine.objects.select_related('category').all()
    # Search
    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(
            Q(name__icontains=q) | Q(generic_name__icontains=q) |
            Q(brand_name__icontains=q)
        )
    # Category filter
    cat = request.GET.get('category', '')
    if cat:
        qs = qs.filter(category_id=cat)
    # Stock status filter
    stock = request.GET.get('stock', '')
    # We need to annotate for stock filtering or do it in-memory

    medicines = paginate_queryset(qs, request, per_page=15)

    # Mark stock status on each item
    for med in medicines:
        med.cached_stock = med.current_stock
        med.cached_is_low = med.is_low_stock
        med.cached_is_over = med.is_overstocked

    categories = MedicineCategory.objects.all()
    context = {
        'medicines': medicines,
        'categories': categories,
        'search_query': q,
        'selected_category': cat,
        'selected_stock': stock,
    }
    return render(request, 'pharmacy/medicine_list.html', context)


@login_required
@role_required('admin', 'staff')
def medicine_detail(request, medicine_id):
    medicine = get_object_or_404(Medicine, pk=medicine_id)
    batches = medicine.batches.all()
    dispensings = Dispensing.objects.filter(
        batch__medicine=medicine
    ).select_related('patient', 'dispensed_by', 'batch')[:20]
    context = {
        'medicine': medicine,
        'batches': batches,
        'dispensings': dispensings,
        'current_stock': medicine.current_stock,
    }
    return render(request, 'pharmacy/medicine_detail.html', context)


@login_required
@role_required('admin', 'staff')
def medicine_create(request):
    if request.method == 'POST':
        form = MedicineForm(request.POST)
        if form.is_valid():
            med = form.save()

            # Audit: medicine catalog entry created
            _log(
                'medicine_added', request.user, medicine=med,
                details=f'Medicine "{med.name}" added to catalog by {request.user}.'
            )

            # Optional opening stock batch
            opening_qty = form.cleaned_data.get('opening_quantity')
            if opening_qty:
                opening_batch = Batch.objects.create(
                    medicine=med,
                    batch_number=form.cleaned_data['opening_batch_number'],
                    quantity=opening_qty,
                    unit_cost=form.cleaned_data.get('opening_unit_cost') or 0,
                    expiry_date=form.cleaned_data['opening_expiry_date'],
                    received_date=timezone.now().date(),
                    notes='Opening stock added during medicine creation.',
                )
                _log(
                    'stock_in', request.user, medicine=med, batch=opening_batch,
                    quantity=opening_qty,
                    details=(
                        f'Opening stock of {opening_qty} unit(s) added for '
                        f'"{med.name}" (Batch {opening_batch.batch_number}).'
                    ),
                )
                messages.success(
                    request,
                    f'Medicine "{med.name}" created with {opening_qty} unit(s) of opening stock.',
                )
            else:
                messages.success(request, f'Medicine "{med.name}" created successfully.')

            return redirect('pharmacy:medicine_detail', medicine_id=med.pk)
    else:
        form = MedicineForm()
    return render(request, 'pharmacy/medicine_form.html', {'form': form, 'title': 'Add Medicine'})


@login_required
@role_required('admin', 'staff')
def medicine_edit(request, medicine_id):
    medicine = get_object_or_404(Medicine, pk=medicine_id)
    if request.method == 'POST':
        form = MedicineForm(request.POST, instance=medicine)
        if form.is_valid():
            form.save()
            messages.success(request, f'Medicine "{medicine.name}" updated.')
            return redirect('pharmacy:medicine_detail', medicine_id=medicine.pk)
    else:
        form = MedicineForm(instance=medicine)
    return render(request, 'pharmacy/medicine_form.html', {
        'form': form, 'title': 'Edit Medicine', 'medicine': medicine,
    })


# ─── Category CRUD ───────────────────────────────────────────────────────────

@login_required
@role_required('admin', 'staff')
def category_list(request):
    categories = MedicineCategory.objects.annotate(
        medicine_count=Count('medicines')
    )
    return render(request, 'pharmacy/category_list.html', {'categories': categories})


@login_required
@role_required('admin', 'staff')
def category_create(request):
    if request.method == 'POST':
        form = MedicineCategoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Category created.')
            return redirect('pharmacy:category_list')
    else:
        form = MedicineCategoryForm()
    return render(request, 'pharmacy/category_form.html', {'form': form, 'title': 'Add Category'})


@login_required
@role_required('admin', 'staff')
def category_edit(request, category_id):
    cat = get_object_or_404(MedicineCategory, pk=category_id)
    if request.method == 'POST':
        form = MedicineCategoryForm(request.POST, instance=cat)
        if form.is_valid():
            form.save()
            messages.success(request, 'Category updated.')
            return redirect('pharmacy:category_list')
    else:
        form = MedicineCategoryForm(instance=cat)
    return render(request, 'pharmacy/category_form.html', {
        'form': form, 'title': 'Edit Category', 'category': cat,
    })


@login_required
@role_required('admin', 'staff')
def category_delete(request, category_id):
    cat = get_object_or_404(MedicineCategory, pk=category_id)
    if request.method == 'POST':
        cat.delete()
        messages.success(request, 'Category deleted.')
        return redirect('pharmacy:category_list')
    return render(request, 'pharmacy/category_confirm_delete.html', {'category': cat})


# ─── Batch Management ────────────────────────────────────────────────────────

@login_required
@role_required('admin', 'staff')
def batch_list(request):
    qs = Batch.objects.select_related('medicine').all()
    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(
            Q(batch_number__icontains=q) | Q(medicine__name__icontains=q)
        )
    status = request.GET.get('status', '')
    today = timezone.now().date()
    if status == 'expired':
        qs = qs.filter(expiry_date__lte=today)
    elif status == 'near_expiry':
        qs = qs.filter(expiry_date__gt=today, expiry_date__lte=today + timezone.timedelta(days=90))
    elif status == 'ok':
        qs = qs.filter(expiry_date__gt=today + timezone.timedelta(days=90))

    batches = paginate_queryset(qs, request, per_page=15)
    context = {
        'batches': batches,
        'search_query': q,
        'selected_status': status,
    }
    return render(request, 'pharmacy/batch_list.html', context)


@login_required
@role_required('admin', 'staff')
def batch_create(request):
    if request.method == 'POST':
        form = BatchForm(request.POST)
        if form.is_valid():
            batch = form.save()
            _log('stock_in', request.user, batch.medicine, batch,
                 batch.quantity, f'New batch {batch.batch_number} added with {batch.quantity} units.')
            messages.success(request, f'Batch "{batch.batch_number}" created.')
            return redirect('pharmacy:batch_list')
    else:
        form = BatchForm()
    return render(request, 'pharmacy/batch_form.html', {'form': form, 'title': 'Add Batch'})


@login_required
@role_required('admin', 'staff')
def batch_edit(request, batch_id):
    batch = get_object_or_404(Batch, pk=batch_id)
    old_qty = batch.quantity
    if request.method == 'POST':
        form = BatchForm(request.POST, instance=batch)
        if form.is_valid():
            form.save()
            if batch.quantity != old_qty:
                _log('adjustment', request.user, batch.medicine, batch,
                     batch.quantity - old_qty, f'Batch {batch.batch_number} edited. Qty {old_qty}→{batch.quantity}.')
            messages.success(request, f'Batch "{batch.batch_number}" updated.')
            return redirect('pharmacy:batch_list')
    else:
        form = BatchForm(instance=batch)
    return render(request, 'pharmacy/batch_form.html', {
        'form': form, 'title': 'Edit Batch', 'batch': batch,
    })


# ─── Supplier Management ─────────────────────────────────────────────────────

@login_required
@role_required('admin', 'staff')
def supplier_list(request):
    qs = Supplier.objects.annotate(order_count=Count('purchase_orders')).order_by('name', 'id')
    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(contact_person__icontains=q))
    suppliers = paginate_queryset(qs, request, per_page=15)
    return render(request, 'pharmacy/supplier_list.html', {
        'suppliers': suppliers, 'search_query': q,
    })


@login_required
@role_required('admin', 'staff')
def supplier_create(request):
    if request.method == 'POST':
        form = SupplierForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Supplier created.')
            return redirect('pharmacy:supplier_list')
    else:
        form = SupplierForm()
    return render(request, 'pharmacy/supplier_form.html', {'form': form, 'title': 'Add Supplier'})


@login_required
@role_required('admin', 'staff')
def supplier_edit(request, supplier_id):
    supplier = get_object_or_404(Supplier, pk=supplier_id)
    if request.method == 'POST':
        form = SupplierForm(request.POST, instance=supplier)
        if form.is_valid():
            form.save()
            messages.success(request, 'Supplier updated.')
            return redirect('pharmacy:supplier_list')
    else:
        form = SupplierForm(instance=supplier)
    return render(request, 'pharmacy/supplier_form.html', {
        'form': form, 'title': 'Edit Supplier', 'supplier': supplier,
    })


# ─── Purchase Orders ─────────────────────────────────────────────────────────

@login_required
@role_required('admin', 'staff')
def purchase_order_list(request):
    qs = PurchaseOrder.objects.select_related('supplier', 'ordered_by').all()
    status = request.GET.get('status', '')
    if status:
        qs = qs.filter(status=status)
    orders = paginate_queryset(qs, request, per_page=15)
    return render(request, 'pharmacy/purchase_order_list.html', {
        'orders': orders, 'selected_status': status,
    })


@login_required
@role_required('admin', 'staff')
def purchase_order_create(request):
    if request.method == 'POST':
        form = PurchaseOrderForm(request.POST)
        formset = PurchaseOrderItemFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                po = form.save(commit=False)
                po.ordered_by = request.user
                po.save()
                formset.instance = po
                formset.save()
                _log('order_created', request.user, details=f'PO {po.order_number} created for {po.supplier.name}.')
            messages.success(request, f'Purchase Order {po.order_number} created.')
            return redirect('pharmacy:purchase_order_detail', order_id=po.pk)
    else:
        form = PurchaseOrderForm()
        formset = PurchaseOrderItemFormSet()
    return render(request, 'pharmacy/purchase_order_form.html', {
        'form': form, 'formset': formset, 'title': 'Create Purchase Order',
    })


@login_required
@role_required('admin', 'staff')
def purchase_order_detail(request, order_id):
    order = get_object_or_404(
        PurchaseOrder.objects.select_related('supplier', 'ordered_by', 'approved_by'),
        pk=order_id
    )
    items = order.items.select_related('medicine').all()
    return render(request, 'pharmacy/purchase_order_detail.html', {
        'order': order, 'items': items,
    })


@login_required
@role_required('admin')
def purchase_order_approve(request, order_id):
    order = get_object_or_404(PurchaseOrder, pk=order_id)
    if request.method == 'POST' and order.status in ('draft', 'submitted'):
        order.status = 'approved'
        order.approved_by = request.user
        order.save()
        _log('order_approved', request.user,
             details=f'PO {order.order_number} approved.')
        messages.success(request, f'PO {order.order_number} approved.')
    return redirect('pharmacy:purchase_order_detail', order_id=order.pk)


@login_required
@role_required('admin', 'staff')
def purchase_order_receive(request, order_id):
    order = get_object_or_404(PurchaseOrder, pk=order_id)
    if request.method == 'POST' and order.status == 'approved':
        with transaction.atomic():
            for item in order.items.select_related('medicine').all():
                # Create or update batch
                batch, created = Batch.objects.get_or_create(
                    medicine=item.medicine,
                    batch_number=f"PO-{order.order_number}-{item.pk}",
                    defaults={
                        'quantity': item.quantity_ordered,
                        'unit_cost': item.unit_cost,
                        'expiry_date': timezone.now().date() + timezone.timedelta(days=730),  # default 2 years
                        'received_date': timezone.now().date(),
                    }
                )
                if not created:
                    batch.quantity += item.quantity_ordered
                    batch.save()
                item.quantity_received = item.quantity_ordered
                item.save()
                _log('stock_in', request.user, item.medicine, batch,
                     item.quantity_ordered,
                     f'Received {item.quantity_ordered} units from PO {order.order_number}.')
            order.status = 'received'
            order.received_date = timezone.now().date()
            order.save()
            _log('order_received', request.user,
                 details=f'PO {order.order_number} fully received.')
        messages.success(request, f'PO {order.order_number} received and stock updated.')
    return redirect('pharmacy:purchase_order_detail', order_id=order.pk)


# ─── Dispensing ──────────────────────────────────────────────────────────────

@login_required
@role_required('admin', 'staff')
def dispensing_list(request):
    qs = Dispensing.objects.select_related(
        'patient', 'dispensed_by', 'batch__medicine', 'prescribing_doctor'
    ).all()
    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(
            Q(patient__first_name__icontains=q) | Q(patient__last_name__icontains=q) |
            Q(batch__medicine__name__icontains=q) | Q(prescription_reference__icontains=q)
        )
    dispensings = paginate_queryset(qs, request, per_page=15)
    return render(request, 'pharmacy/dispensing_list.html', {
        'dispensings': dispensings, 'search_query': q,
    })


@login_required
@role_required('admin', 'staff')
def dispensing_create(request):
    if request.method == 'POST':
        form = DispensingForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                disp = form.save(commit=False)
                disp.dispensed_by = request.user
                disp.save()
                # Auto-deduct stock
                batch = disp.batch
                batch.quantity -= disp.quantity
                batch.save()
                _log('dispensed', request.user, batch.medicine, batch,
                     disp.quantity,
                     f'Dispensed {disp.quantity} {batch.medicine.unit} of {batch.medicine.name} '
                     f'to {disp.patient.first_name} {disp.patient.last_name}.')
                # Notify patient
                Notification.objects.create(
                    user=disp.patient,
                    title='Medicine Dispensed',
                    message=f'{disp.quantity} {batch.medicine.unit}(s) of {batch.medicine.name} '
                            f'has been dispensed to you.',
                    notification_type='general',
                    transaction_type='general_announcement',
                )
            messages.success(request, 'Medicine dispensed successfully.')
            return redirect('pharmacy:dispensing_list')
    else:
        form = DispensingForm()
    return render(request, 'pharmacy/dispensing_form.html', {
        'form': form, 'title': 'Dispense Medicine',
    })


# ─── Stock Adjustments ──────────────────────────────────────────────────────

@login_required
@role_required('admin', 'staff')
def stock_adjustment_list(request):
    qs = StockAdjustment.objects.select_related(
        'batch__medicine', 'adjusted_by'
    ).all()
    adjustments = paginate_queryset(qs, request, per_page=15)
    return render(request, 'pharmacy/adjustment_list.html', {
        'adjustments': adjustments,
    })


@login_required
@role_required('admin', 'staff')
def stock_adjustment_create(request):
    if request.method == 'POST':
        form = StockAdjustmentForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                adj = form.save(commit=False)
                adj.adjusted_by = request.user
                adj.save()
                batch = adj.batch
                batch.quantity += adj.quantity_change
                batch.save()
                action = 'expired_disposed' if adj.reason == 'expired' else 'adjustment'
                _log(action, request.user, batch.medicine, batch,
                     adj.quantity_change,
                     f'Stock adjustment ({adj.get_reason_display()}): '
                     f'{adj.quantity_change:+d} on {batch.medicine.name} Batch {batch.batch_number}.')
            messages.success(request, 'Stock adjustment recorded.')
            return redirect('pharmacy:adjustment_list')
    else:
        form = StockAdjustmentForm()
    return render(request, 'pharmacy/adjustment_form.html', {
        'form': form, 'title': 'Record Stock Adjustment',
    })


# ─── Audit & Compliance Reports ─────────────────────────────────────────────

@login_required
@role_required('admin', 'staff')
def audit_log_list(request):
    qs = AuditLog.objects.select_related(
        'performed_by', 'medicine', 'batch'
    ).all()
    action = request.GET.get('action', '')
    if action:
        qs = qs.filter(action=action)

    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    if date_from:
        qs = qs.filter(created_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(created_at__date__lte=date_to)

    logs = paginate_queryset(qs, request, per_page=20)
    context = {
        'logs': logs,
        'selected_action': action,
        'action_choices': AuditLog.ACTION_CHOICES,
        'date_from': date_from or '',
        'date_to': date_to or '',
    }
    return render(request, 'pharmacy/audit_log_list.html', context)


@login_required
@role_required('admin')
def compliance_report(request):
    """Generate DOH / CHED compliance summary report."""
    today = timezone.now().date()
    month_start = today.replace(day=1)
    year_start = today.replace(month=1, day=1)

    # Monthly stats
    monthly_dispensed = Dispensing.objects.filter(dispensed_at__date__gte=month_start).aggregate(
        total_qty=Coalesce(Sum('quantity'), 0),
        total_cost=Coalesce(Sum(F('quantity') * F('batch__unit_cost'), output_field=DecimalField()), Decimal('0.00')),
    )
    monthly_procured = PurchaseOrderItem.objects.filter(
        purchase_order__status='received',
        purchase_order__received_date__gte=month_start,
    ).aggregate(
        total_qty=Coalesce(Sum('quantity_ordered'), 0),
        total_cost=Coalesce(Sum(F('quantity_ordered') * F('unit_cost'), output_field=DecimalField()), Decimal('0.00')),
    )

    # Yearly stats
    yearly_dispensed = Dispensing.objects.filter(dispensed_at__date__gte=year_start).aggregate(
        total_qty=Coalesce(Sum('quantity'), 0),
        total_cost=Coalesce(Sum(F('quantity') * F('batch__unit_cost'), output_field=DecimalField()), Decimal('0.00')),
    )
    yearly_procured = PurchaseOrderItem.objects.filter(
        purchase_order__status='received',
        purchase_order__received_date__gte=year_start,
    ).aggregate(
        total_qty=Coalesce(Sum('quantity_ordered'), 0),
        total_cost=Coalesce(Sum(F('quantity_ordered') * F('unit_cost'), output_field=DecimalField()), Decimal('0.00')),
    )

    # Expired inventory
    expired_inventory = Batch.objects.filter(
        quantity__gt=0, expiry_date__lte=today,
    ).select_related('medicine').aggregate(
        count=Count('id'),
        total_qty=Coalesce(Sum('quantity'), 0),
        total_value=Coalesce(Sum(F('quantity') * F('unit_cost'), output_field=DecimalField()), Decimal('0.00')),
    )

    # Top dispensed medicines (year)
    top_dispensed = Dispensing.objects.filter(
        dispensed_at__date__gte=year_start,
    ).values(
        'batch__medicine__name',
    ).annotate(
        total_qty=Sum('quantity'),
    ).order_by('-total_qty')[:10]

    context = {
        'today': today,
        'monthly_dispensed': monthly_dispensed,
        'monthly_procured': monthly_procured,
        'yearly_dispensed': yearly_dispensed,
        'yearly_procured': yearly_procured,
        'expired_inventory': expired_inventory,
        'top_dispensed': top_dispensed,
    }
    return render(request, 'pharmacy/compliance_report.html', context)


# ─── Cost & Budget Analysis ─────────────────────────────────────────────────

@login_required
@role_required('admin', 'staff')
def cost_analysis(request):
    """PHP-denominated cost breakdowns and comparisons."""
    today = timezone.now().date()
    month_start = today.replace(day=1)
    year_start = today.replace(month=1, day=1)

    # Current inventory value
    inventory_value = Batch.objects.filter(quantity__gt=0).aggregate(
        total=Coalesce(Sum(F('quantity') * F('unit_cost'), output_field=DecimalField()), Decimal('0.00'))
    )['total']

    # Monthly procurement by supplier
    supplier_costs = PurchaseOrderItem.objects.filter(
        purchase_order__status='received',
        purchase_order__received_date__gte=month_start,
    ).values(
        'purchase_order__supplier__name',
    ).annotate(
        total_cost=Sum(F('quantity_ordered') * F('unit_cost'), output_field=DecimalField()),
        total_items=Sum('quantity_ordered'),
    ).order_by('-total_cost')

    # Cost per medicine (top 15 by value)
    medicine_costs = Batch.objects.filter(quantity__gt=0).values(
        'medicine__name',
    ).annotate(
        stock_value=Sum(F('quantity') * F('unit_cost'), output_field=DecimalField()),
        total_qty=Sum('quantity'),
    ).order_by('-stock_value')[:15]

    # Monthly expenditure trend (last 6 months)
    from django.db.models.functions import TruncMonth
    monthly_trend = PurchaseOrderItem.objects.filter(
        purchase_order__status='received',
        purchase_order__received_date__gte=year_start,
    ).annotate(
        month=TruncMonth('purchase_order__received_date'),
    ).values('month').annotate(
        total=Sum(F('quantity_ordered') * F('unit_cost'), output_field=DecimalField()),
    ).order_by('month')

    context = {
        'inventory_value': inventory_value,
        'supplier_costs': supplier_costs,
        'medicine_costs': medicine_costs,
        'monthly_trend': list(monthly_trend),
    }
    return render(request, 'pharmacy/cost_analysis.html', context)


# ─── AJAX Endpoints ─────────────────────────────────────────────────────────

@login_required
def api_batches_for_medicine(request, medicine_id):
    """Return available batches for a given medicine (for dispensing form JS)."""
    batches = Batch.objects.filter(
        medicine_id=medicine_id, quantity__gt=0,
        expiry_date__gt=timezone.now().date(),
    ).order_by('expiry_date')
    data = [
        {
            'id': b.id,
            'batch_number': b.batch_number,
            'quantity': b.quantity,
            'expiry_date': b.expiry_date.isoformat(),
            'unit_cost': str(b.unit_cost),
        }
        for b in batches
    ]
    return JsonResponse(data, safe=False)
