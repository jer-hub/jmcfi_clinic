from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from core.decorators import role_required

from pharmacy.services.reports import build_compliance_context, build_cost_analysis_context


@login_required
@role_required('staff')
def compliance_report(request):
    """Generate DOH / CHED compliance summary report."""
    return render(request, 'pharmacy/compliance_report.html', build_compliance_context())


@login_required
@role_required('staff')
def cost_analysis(request):
    """PHP-denominated cost breakdowns and comparisons."""
    return render(request, 'pharmacy/cost_analysis.html', build_cost_analysis_context())
