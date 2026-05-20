from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from core.decorators import role_required
from core.htmx_utils import htmx_add_toast, htmx_redirect, is_htmx_request
from core.utils import paginate_queryset

from pharmacy.forms import PurchaseOrderForm, PurchaseOrderItemFormSet, SupplierForm
from pharmacy.htmx_lists import list_querystring, render_list
from pharmacy.models import PurchaseOrder, Supplier
from pharmacy.services.orders import (
    approve_purchase_order,
    create_purchase_order,
    receive_purchase_order,
)


@login_required
@role_required('staff')
def supplier_list(request):
    qs = Supplier.objects.annotate(order_count=Count('purchase_orders')).order_by('name', 'id')
    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(contact_person__icontains=q))
    return render(
        request,
        'pharmacy/supplier_list.html',
        {'suppliers': paginate_queryset(qs, request, per_page=15), 'search_query': q},
    )


@login_required
@role_required('staff')
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
@role_required('staff')
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
    return render(
        request,
        'pharmacy/supplier_form.html',
        {'form': form, 'title': 'Edit Supplier', 'supplier': supplier},
    )


def _build_purchase_order_list_context(request):
    qs = PurchaseOrder.objects.select_related('supplier', 'ordered_by').order_by('-order_date', '-id')
    status = request.GET.get('status', '')
    if status:
        qs = qs.filter(status=status)
    return {
        'orders': paginate_queryset(qs, request, per_page=15),
        'selected_status': status,
        'list_querystring': list_querystring(request.GET),
    }


@login_required
@role_required('staff')
def purchase_order_list(request):
    context = _build_purchase_order_list_context(request)
    return render_list(
        request,
        full_template='pharmacy/purchase_order_list.html',
        oob_template='pharmacy/_purchase_order_list_filter_oob.html',
        context=context,
    )


@login_required
@role_required('staff')
def purchase_order_create(request):
    if request.method == 'POST':
        form = PurchaseOrderForm(request.POST)
        formset = PurchaseOrderItemFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            po = create_purchase_order(form=form, formset=formset, user=request.user)
            messages.success(request, f'Purchase Order {po.order_number} created.')
            return redirect('pharmacy:purchase_order_detail', order_id=po.pk)
    else:
        form = PurchaseOrderForm()
        formset = PurchaseOrderItemFormSet()
    return render(
        request,
        'pharmacy/purchase_order_form.html',
        {'form': form, 'formset': formset, 'title': 'Create Purchase Order'},
    )


@login_required
@role_required('staff')
def purchase_order_detail(request, order_id):
    order = get_object_or_404(
        PurchaseOrder.objects.select_related('supplier', 'ordered_by', 'approved_by'),
        pk=order_id,
    )
    return render(
        request,
        'pharmacy/purchase_order_detail.html',
        {'order': order, 'items': order.items.select_related('medicine').all()},
    )


@login_required
@role_required('staff')
def purchase_order_approve(request, order_id):
    order = get_object_or_404(PurchaseOrder, pk=order_id)
    if request.method == 'POST':
        if approve_purchase_order(order, request.user):
            msg = f'PO {order.order_number} approved.'
            if is_htmx_request(request):
                detail_url = reverse('pharmacy:purchase_order_detail', kwargs={'order_id': order.pk})
                return htmx_add_toast(htmx_redirect(detail_url), msg)
            messages.success(request, msg)
        elif is_htmx_request(request):
            return htmx_add_toast(HttpResponse(status=400), 'Order cannot be approved.', 'error')
    return redirect('pharmacy:purchase_order_detail', order_id=order.pk)


@login_required
@role_required('staff')
def purchase_order_receive(request, order_id):
    order = get_object_or_404(PurchaseOrder, pk=order_id)
    if request.method == 'POST':
        if receive_purchase_order(order, request.user):
            msg = f'PO {order.order_number} received and stock updated.'
            if is_htmx_request(request):
                detail_url = reverse('pharmacy:purchase_order_detail', kwargs={'order_id': order.pk})
                return htmx_add_toast(htmx_redirect(detail_url), msg)
            messages.success(request, msg)
        elif is_htmx_request(request):
            return htmx_add_toast(HttpResponse(status=400), 'Order cannot be received.', 'error')
    return redirect('pharmacy:purchase_order_detail', order_id=order.pk)
