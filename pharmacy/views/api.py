from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from core.decorators import role_required
from core.htmx_utils import is_htmx_request

from pharmacy.models import Batch, Medicine
from pharmacy.services.stock import available_batches_payload, medicine_detail_payload


@login_required
@role_required('staff')
def api_batches_for_medicine(request, medicine_id):
    """Return available batches for dispensing (HTML options for HTMX, JSON for legacy)."""
    today = timezone.now().date()
    batches = Batch.objects.filter(
        medicine_id=medicine_id,
        quantity__gt=0,
        expiry_date__gt=today,
    ).order_by('expiry_date')
    if is_htmx_request(request):
        return render(request, 'pharmacy/_batch_select_options.html', {'batches': batches})
    return JsonResponse(available_batches_payload(medicine_id), safe=False)


@login_required
@role_required('staff')
def api_medicine_detail(request, medicine_id):
    """Return medicine metadata for dispensing summary card (JSON)."""
    medicine = get_object_or_404(Medicine, pk=medicine_id, is_active=True)
    return JsonResponse(medicine_detail_payload(medicine))
