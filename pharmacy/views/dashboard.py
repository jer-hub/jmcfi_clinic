from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from core.decorators import role_required

from pharmacy.services.reports import build_dashboard_context


@login_required
@role_required('staff')
def pharmacy_dashboard(request):
    """Pharmacy overview with KPIs and alerts."""
    return render(request, 'pharmacy/dashboard.html', build_dashboard_context())
