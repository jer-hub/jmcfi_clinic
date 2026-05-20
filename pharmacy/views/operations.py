from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.shortcuts import redirect, render

from core.decorators import role_required
from core.utils import paginate_queryset

from pharmacy.forms import DispensingForm, StockAdjustmentForm
from pharmacy.models import AuditLog, Dispensing, StockAdjustment
from pharmacy.services.stock import apply_stock_adjustment, dispense_and_deduct


@login_required
@role_required('staff')
def dispensing_list(request):
    qs = Dispensing.objects.select_related(
        'patient', 'dispensed_by', 'batch__medicine', 'prescribing_doctor',
    ).all()
    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(
            Q(patient__first_name__icontains=q)
            | Q(patient__last_name__icontains=q)
            | Q(batch__medicine__name__icontains=q)
            | Q(prescription_reference__icontains=q)
        )
    return render(
        request,
        'pharmacy/dispensing_list.html',
        {'dispensings': paginate_queryset(qs, request, per_page=15), 'search_query': q},
    )


@login_required
@role_required('staff')
def dispensing_create(request):
    if request.method == 'POST':
        form = DispensingForm(request.POST)
        if form.is_valid():
            try:
                disp = form.save(commit=False)
                dispense_and_deduct(disp, request.user)
            except ValidationError as exc:
                msg = exc.messages[0] if getattr(exc, 'messages', None) else str(exc)
                messages.error(request, msg)
            else:
                messages.success(request, 'Medicine dispensed successfully.')
                return redirect('pharmacy:dispensing_list')
    else:
        form = DispensingForm()
    return render(request, 'pharmacy/dispensing_form.html', {'form': form, 'title': 'Dispense Medicine'})


@login_required
@role_required('staff')
def stock_adjustment_list(request):
    qs = StockAdjustment.objects.select_related('batch__medicine', 'adjusted_by').all()
    return render(
        request,
        'pharmacy/adjustment_list.html',
        {'adjustments': paginate_queryset(qs, request, per_page=15)},
    )


@login_required
@role_required('staff')
def stock_adjustment_create(request):
    if request.method == 'POST':
        form = StockAdjustmentForm(request.POST)
        if form.is_valid():
            try:
                adj = form.save(commit=False)
                apply_stock_adjustment(adj, request.user)
            except ValidationError as exc:
                msg = exc.messages[0] if getattr(exc, 'messages', None) else str(exc)
                messages.error(request, msg)
            else:
                messages.success(request, 'Stock adjustment recorded.')
                return redirect('pharmacy:adjustment_list')
    else:
        form = StockAdjustmentForm()
    return render(
        request,
        'pharmacy/adjustment_form.html',
        {'form': form, 'title': 'Record Stock Adjustment'},
    )


@login_required
@role_required('staff')
def audit_log_list(request):
    qs = AuditLog.objects.select_related('performed_by', 'medicine', 'batch').all()
    action = request.GET.get('action', '')
    if action:
        qs = qs.filter(action=action)

    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    if date_from:
        qs = qs.filter(created_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(created_at__date__lte=date_to)

    return render(
        request,
        'pharmacy/audit_log_list.html',
        {
            'logs': paginate_queryset(qs, request, per_page=20),
            'selected_action': action,
            'action_choices': AuditLog.ACTION_CHOICES,
            'date_from': date_from or '',
            'date_to': date_to or '',
        },
    )
