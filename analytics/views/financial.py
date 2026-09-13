"""Financial & cost analysis views."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from core.decorators import admin_required
from core.utils import paginate_queryset

from analytics.academic_filters import (
    analytics_filter_context,
    filtered_clinical_counts,
    page_window_numbers,
)
from analytics.forms import FinancialRecordForm
from analytics.models import FinancialRecord
from analytics.services import financial_summary, fmt_peso
from analytics.views.helpers import (
    _filters_from_request,
    _get_date_range,
    _period_presets_for_request,
)


@login_required
@admin_required
def financial_overview(request):
    """Financial overview dashboard."""
    date_from, date_to = _get_date_range(request)
    filters = _filters_from_request(request)
    summary = financial_summary(date_from, date_to)
    clinical = filtered_clinical_counts(date_from, date_to, filters)
    records_qs = FinancialRecord.objects.filter(
        date__gte=date_from, date__lte=date_to,
    ).order_by('-date', '-id')
    records_page = paginate_queryset(records_qs, request, per_page=15)

    context = {
        'summary': summary,
        'records': records_page,
        'page_window': page_window_numbers(records_page),
        'records_count': records_qs.count(),
        'date_from': date_from,
        'date_to': date_to,
        'period_hint': f'{date_from.strftime("%b %d")} – {date_to.strftime("%b %d")}',
        'expenses_display': fmt_peso(summary['total_expenses']),
        'income_display': fmt_peso(summary['total_income']),
        'net_display': fmt_peso(summary['net']),
        'net_variant': 'success' if summary['net'] >= 0 else 'danger',
        'filtered_appointments': clinical['filtered_appointments'],
        'filtered_medical_records': clinical['filtered_medical_records'],
        'export_variant': 'financial',
    }
    context.update(analytics_filter_context(request, date_from, date_to))
    context['period_presets'] = _period_presets_for_request(request, date_from, date_to)
    return render(request, 'analytics/financial_overview.html', context)


@login_required
@admin_required
def financial_record_create(request):
    """Create a financial record."""
    if request.method == 'POST':
        form = FinancialRecordForm(request.POST)
        if form.is_valid():
            record = form.save(commit=False)
            record.recorded_by = request.user
            record.save()
            messages.success(request, 'Financial record added successfully.')
            return redirect('analytics:financial_overview')
    else:
        form = FinancialRecordForm()
    return render(request, 'analytics/financial_record_form.html', {'form': form})
