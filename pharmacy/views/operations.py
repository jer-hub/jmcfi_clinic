from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.shortcuts import redirect, render
from django.urls import reverse

from core.decorators import role_required
from core.roles import PATIENT_ROLE_VALUES
from core.utils import paginate_queryset, student_display_name

from pharmacy.forms import DispensingForm, StockAdjustmentForm
from pharmacy.models import AuditLog, Dispensing, StockAdjustment
from pharmacy.services.stock import apply_stock_adjustment, dispense_and_deduct

User = get_user_model()


def _dispensing_patient_payload(user):
    profile = getattr(user, 'patient_profile', None)
    return {
        'id': user.id,
        'name': student_display_name(user),
        'email': user.email,
        'patient_id': getattr(profile, 'patient_id', '') if profile else '',
    }


def _resolve_selected_patient(request, form=None):
    patient_pk = None
    if form is not None and form.is_bound and form.data.get('patient'):
        patient_pk = form.data.get('patient')
    elif request.method == 'GET':
        patient_pk = request.GET.get('patient', '').strip()
    if not patient_pk:
        return None
    try:
        patient = User.objects.select_related('patient_profile').get(
            pk=int(patient_pk),
            role__in=PATIENT_ROLE_VALUES,
            is_active=True,
        )
    except (User.DoesNotExist, ValueError, TypeError):
        return None
    return _dispensing_patient_payload(patient)


def _dispensing_form_context(request, form):
    return {
        'form': form,
        'title': 'Dispense Medicine',
        'patient_search_url': reverse('core:search_patients'),
        'selected_patient': _resolve_selected_patient(request, form),
        'recent_dispensings': Dispensing.objects.select_related(
            'patient', 'batch__medicine', 'dispensed_by',
        ).order_by('-dispensed_at')[:8],
        'medicine_api_base': reverse(
            'pharmacy:api_medicine_detail',
            kwargs={'medicine_id': 0},
        ),
        'batch_api_base': reverse(
            'pharmacy:api_batches_for_medicine',
            kwargs={'medicine_id': 0},
        ),
    }


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
    return render(request, 'pharmacy/dispensing_form.html', _dispensing_form_context(request, form))


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
