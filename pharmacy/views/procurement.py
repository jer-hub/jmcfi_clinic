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
from pharmacy.models import Medicine, PurchaseOrder, Supplier
from pharmacy.services.orders import (
    approve_purchase_order,
    create_purchase_order,
    receive_purchase_order,
    submit_purchase_order,
    update_purchase_order,
)
from pharmacy.services.stock import low_stock_medicines


def suggested_reorder_qty(medicine) -> int:
    return max(1, medicine.reorder_level * 2 - medicine.current_stock)


def _build_reorder_prefill_lines(request):
  lines = []
  if request.GET.get('reorder') == '1':
    _, items = low_stock_medicines(limit=10)
    for med in items:
      lines.append({
        'medicine': med.pk,
        'quantity_ordered': suggested_reorder_qty(med),
        'unit_cost': '0.00',
      })
  medicines_param = request.GET.get('medicines', '').strip()
  if medicines_param:
    existing_ids = {line['medicine'] for line in lines}
    for part in medicines_param.split(','):
      part = part.strip()
      if not part.isdigit():
        continue
      med_id = int(part)
      if med_id in existing_ids:
        continue
      try:
        med = Medicine.objects.get(pk=med_id, is_active=True)
      except Medicine.DoesNotExist:
        continue
      lines.append({
        'medicine': med.pk,
        'quantity_ordered': suggested_reorder_qty(med),
        'unit_cost': '0.00',
      })
      existing_ids.add(med_id)
  return lines


def _resolve_supplier_prefill(request):
  supplier_pk = request.GET.get('supplier', '').strip()
  if not supplier_pk or not supplier_pk.isdigit():
    return None
  try:
    return Supplier.objects.get(pk=int(supplier_pk), is_active=True)
  except Supplier.DoesNotExist:
    return None


def _low_stock_sidebar_items():
  _, items = low_stock_medicines(limit=8)
  return [
    {
      'id': med.pk,
      'name': str(med),
      'current_stock': med.current_stock,
      'unit_display': med.get_unit_display(),
      'reorder_level': med.reorder_level,
      'suggested_qty': suggested_reorder_qty(med),
    }
    for med in items
  ]


def _purchase_order_form_context(request, *, form, formset, title, order=None):
  prefill_supplier = _resolve_supplier_prefill(request)
  if order is not None:
    prefill_supplier = order.supplier
  prefill_lines = _build_reorder_prefill_lines(request) if order is None else []
  return {
    'form': form,
    'formset': formset,
    'title': title,
    'order': order,
    'prefill_supplier': prefill_supplier,
    'prefill_lines': prefill_lines,
    'reorder_prefill': bool(prefill_lines),
    'low_stock_items': _low_stock_sidebar_items(),
    'is_edit': order is not None,
  }


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
def supplier_detail(request, supplier_id):
  supplier = get_object_or_404(
    Supplier.objects.annotate(order_count=Count('purchase_orders')),
    pk=supplier_id,
  )
  recent_orders = (
    PurchaseOrder.objects.filter(supplier=supplier)
    .select_related('ordered_by')
    .order_by('-order_date', '-id')[:10]
  )
  return render(
    request,
    'pharmacy/supplier_detail.html',
    {'supplier': supplier, 'recent_orders': recent_orders},
  )


@login_required
@role_required('staff')
def supplier_create(request):
  if request.method == 'POST':
    form = SupplierForm(request.POST)
    if form.is_valid():
      supplier = form.save()
      messages.success(request, 'Supplier created.')
      return redirect('pharmacy:supplier_detail', supplier_id=supplier.pk)
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
      return redirect('pharmacy:supplier_detail', supplier_id=supplier.pk)
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
  q = request.GET.get('q', '').strip()
  if status:
    qs = qs.filter(status=status)
  if q:
    qs = qs.filter(
      Q(order_number__icontains=q)
      | Q(supplier__name__icontains=q)
    )
  return {
    'orders': paginate_queryset(qs, request, per_page=15),
    'selected_status': status,
    'search_query': q,
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
    initial = {}
    prefill_supplier = _resolve_supplier_prefill(request)
    if prefill_supplier:
      initial['supplier'] = prefill_supplier.pk
    form = PurchaseOrderForm(initial=initial)
    prefill_lines = _build_reorder_prefill_lines(request)
    if prefill_lines:
      formset = PurchaseOrderItemFormSet(initial=prefill_lines)
    else:
      formset = PurchaseOrderItemFormSet()
  return render(
    request,
    'pharmacy/purchase_order_form.html',
    _purchase_order_form_context(request, form=form, formset=formset, title='Create Purchase Order'),
  )


@login_required
@role_required('staff')
def purchase_order_edit(request, order_id):
  order = get_object_or_404(PurchaseOrder, pk=order_id)
  if order.status != 'draft':
    messages.error(request, 'Only draft purchase orders can be edited.')
    return redirect('pharmacy:purchase_order_detail', order_id=order.pk)
  if request.method == 'POST':
    form = PurchaseOrderForm(request.POST, instance=order)
    formset = PurchaseOrderItemFormSet(request.POST, instance=order)
    if form.is_valid() and formset.is_valid():
      try:
        update_purchase_order(order=order, form=form, formset=formset, user=request.user)
      except ValueError as exc:
        messages.error(request, str(exc))
      else:
        messages.success(request, f'Purchase Order {order.order_number} updated.')
        return redirect('pharmacy:purchase_order_detail', order_id=order.pk)
  else:
    form = PurchaseOrderForm(instance=order)
    formset = PurchaseOrderItemFormSet(instance=order)
  return render(
    request,
    'pharmacy/purchase_order_form.html',
    _purchase_order_form_context(
      request, form=form, formset=formset, title='Edit Purchase Order', order=order,
    ),
  )


def _purchase_order_workflow_context(order):
    status_order = ['draft', 'submitted', 'approved', 'received']
    labels = dict(PurchaseOrder.STATUS_CHOICES)
    current_idx = status_order.index(order.status) if order.status in status_order else -1
    workflow_steps = []
    for idx, key in enumerate(status_order):
        workflow_steps.append({
            'key': key,
            'label': labels.get(key, key.title()),
            'is_current': order.status == key,
            'is_complete': current_idx >= 0 and idx < current_idx,
        })
    return {'workflow_steps': workflow_steps}


@login_required
@role_required('staff')
def purchase_order_detail(request, order_id):
    order = get_object_or_404(
        PurchaseOrder.objects.select_related('supplier', 'ordered_by', 'approved_by'),
        pk=order_id,
    )
    context = {
        'order': order,
        'items': order.items.select_related('medicine').all(),
    }
    context.update(_purchase_order_workflow_context(order))
    return render(request, 'pharmacy/purchase_order_detail.html', context)


@login_required
@role_required('staff')
def purchase_order_submit(request, order_id):
  order = get_object_or_404(PurchaseOrder, pk=order_id)
  if request.method == 'POST':
    if submit_purchase_order(order, request.user):
      msg = f'PO {order.order_number} submitted for approval.'
      if is_htmx_request(request):
        detail_url = reverse('pharmacy:purchase_order_detail', kwargs={'order_id': order.pk})
        return htmx_add_toast(htmx_redirect(detail_url), msg)
      messages.success(request, msg)
    elif is_htmx_request(request):
      return htmx_add_toast(HttpResponse(status=400), 'Order cannot be submitted.', 'error')
    else:
      messages.error(request, 'Order cannot be submitted.')
  return redirect('pharmacy:purchase_order_detail', order_id=order.pk)


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
