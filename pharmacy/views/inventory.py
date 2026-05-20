from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, F, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from core.decorators import role_required
from core.utils import paginate_queryset

from pharmacy.forms import BatchForm, MedicineCategoryForm, MedicineForm
from pharmacy.htmx_lists import list_querystring, render_list
from pharmacy.models import Batch, Dispensing, Medicine, MedicineCategory
from pharmacy.services.stock import (
    create_opening_stock,
    log_batch_quantity_edit,
    log_batch_stock_in,
    log_medicine_added,
)


def _build_medicine_list_context(request):
    qs = Medicine.objects.filter(is_active=True).select_related('category')
    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(
            Q(name__icontains=q)
            | Q(generic_name__icontains=q)
            | Q(brand_name__icontains=q)
        )
    cat = request.GET.get('category', '')
    if cat:
        qs = qs.filter(category_id=cat)
    stock = request.GET.get('stock', '')
    if stock == 'low':
        qs = qs.filter(cached_non_expired_stock__lte=F('reorder_level'))
    elif stock == 'over':
        qs = qs.filter(cached_non_expired_stock__gt=F('max_stock_level'))

    medicines = paginate_queryset(qs.order_by('name'), request, per_page=15)
    for med in medicines:
        med.cached_stock = med.cached_non_expired_stock
        med.cached_is_low = med.cached_non_expired_stock <= med.reorder_level
        med.cached_is_over = med.cached_non_expired_stock > med.max_stock_level

    return {
        'medicines': medicines,
        'categories': MedicineCategory.objects.all(),
        'search_query': q,
        'selected_category': cat,
        'selected_stock': stock,
        'list_querystring': list_querystring(request.GET),
    }


@login_required
@role_required('staff')
def medicine_list(request):
    context = _build_medicine_list_context(request)
    return render_list(
        request,
        full_template='pharmacy/medicine_list.html',
        oob_template='pharmacy/_medicine_list_filter_oob.html',
        context=context,
    )


@login_required
@role_required('staff')
def medicine_detail(request, medicine_id):
    medicine = get_object_or_404(Medicine, pk=medicine_id)
    return render(
        request,
        'pharmacy/medicine_detail.html',
        {
            'medicine': medicine,
            'batches': medicine.batches.all(),
            'dispensings': Dispensing.objects.filter(batch__medicine=medicine).select_related(
                'patient', 'dispensed_by', 'batch',
            )[:20],
            'current_stock': medicine.current_stock,
        },
    )


@login_required
@role_required('staff')
def medicine_create(request):
    if request.method == 'POST':
        form = MedicineForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                med = form.save()
                log_medicine_added(med, request.user)
                opening_batch = create_opening_stock(med, form.cleaned_data, request.user)
            if opening_batch:
                messages.success(
                    request,
                    f'Medicine "{med.name}" created with {opening_batch.quantity} unit(s) of opening stock.',
                )
            else:
                messages.success(request, f'Medicine "{med.name}" created successfully.')
            return redirect('pharmacy:medicine_detail', medicine_id=med.pk)
    else:
        form = MedicineForm()
    return render(request, 'pharmacy/medicine_form.html', {'form': form, 'title': 'Add Medicine'})


@login_required
@role_required('staff')
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
    return render(
        request,
        'pharmacy/medicine_form.html',
        {'form': form, 'title': 'Edit Medicine', 'medicine': medicine},
    )


@login_required
@role_required('staff')
def category_list(request):
    categories = MedicineCategory.objects.annotate(medicine_count=Count('medicines'))
    return render(request, 'pharmacy/category_list.html', {'categories': categories})


@login_required
@role_required('staff')
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
@role_required('staff')
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
    return render(
        request,
        'pharmacy/category_form.html',
        {'form': form, 'title': 'Edit Category', 'category': cat},
    )


@login_required
@role_required('staff')
def category_delete(request, category_id):
    cat = get_object_or_404(MedicineCategory, pk=category_id)
    if request.method == 'POST':
        cat.delete()
        messages.success(request, 'Category deleted.')
        return redirect('pharmacy:category_list')
    return render(request, 'pharmacy/category_confirm_delete.html', {'category': cat})


def _build_batch_list_context(request):
    qs = Batch.objects.select_related('medicine').order_by('expiry_date', 'medicine__name')
    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(Q(batch_number__icontains=q) | Q(medicine__name__icontains=q))
    status = request.GET.get('status', '')
    today = timezone.now().date()
    if status == 'expired':
        qs = qs.filter(expiry_date__lte=today)
    elif status == 'near_expiry':
        qs = qs.filter(expiry_date__gt=today, expiry_date__lte=today + timezone.timedelta(days=90))
    elif status == 'ok':
        qs = qs.filter(expiry_date__gt=today + timezone.timedelta(days=90))

    return {
        'batches': paginate_queryset(qs, request, per_page=15),
        'search_query': q,
        'selected_status': status,
        'list_querystring': list_querystring(request.GET),
    }


@login_required
@role_required('staff')
def batch_list(request):
    context = _build_batch_list_context(request)
    return render_list(
        request,
        full_template='pharmacy/batch_list.html',
        oob_template='pharmacy/_batch_list_filter_oob.html',
        context=context,
    )


@login_required
@role_required('staff')
def batch_create(request):
    if request.method == 'POST':
        form = BatchForm(request.POST)
        if form.is_valid():
            batch = form.save()
            log_batch_stock_in(batch, request.user)
            messages.success(request, f'Batch "{batch.batch_number}" created.')
            return redirect('pharmacy:batch_list')
    else:
        form = BatchForm()
    return render(request, 'pharmacy/batch_form.html', {'form': form, 'title': 'Add Batch'})


@login_required
@role_required('staff')
def batch_edit(request, batch_id):
    batch = get_object_or_404(Batch, pk=batch_id)
    old_qty = batch.quantity
    if request.method == 'POST':
        form = BatchForm(request.POST, instance=batch)
        if form.is_valid():
            form.save()
            log_batch_quantity_edit(batch, request.user, old_qty)
            messages.success(request, f'Batch "{batch.batch_number}" updated.')
            return redirect('pharmacy:batch_list')
    else:
        form = BatchForm(instance=batch)
    return render(
        request,
        'pharmacy/batch_form.html',
        {'form': form, 'title': 'Edit Batch', 'batch': batch},
    )
