"""Page-level dental chart tooth add/delete views (edit form)."""

import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from core.decorators import role_required
from dental_records.models import DentalChart, DentalRecord


@login_required
@role_required('doctor')
def dental_chart_add_tooth(request, record_id):
    """Add or update a tooth in the dental chart"""
    dental_record = get_object_or_404(DentalRecord, pk=record_id)
    
    if request.method == 'POST':
        tooth_number = request.POST.get('tooth_number')
        
        # Check if tooth already exists
        tooth, created = DentalChart.objects.get_or_create(
            dental_record=dental_record,
            tooth_number=tooth_number,
            defaults={
                'tooth_type': request.POST.get('tooth_type', 'permanent'),
                'condition': request.POST.get('condition', 'healthy'),
                'notes': request.POST.get('notes', '')
            }
        )
        
        if not created:
            # Update existing tooth
            tooth.tooth_type = request.POST.get('tooth_type', tooth.tooth_type)
            tooth.condition = request.POST.get('condition', tooth.condition)
            tooth.notes = request.POST.get('notes', tooth.notes)
            tooth.save()
        
        # If HTMX request, return partial template without adding Django messages
        if request.headers.get('HX-Request'):
            dental_chart = dental_record.dental_chart.prefetch_related('surfaces').order_by('tooth_number')
            return render(request, 'dental_records/partials/dental_chart_table.html', {
                'dental_chart': dental_chart,
                'dental_record': dental_record,
            })
        
        # Only add messages for non-HTMX requests
        messages.success(request, f'Tooth #{tooth_number} {"added" if created else "updated"} successfully.')
        return redirect('dental_records:dental_record_edit', record_id=record_id)
    
    return redirect('dental_records:dental_record_edit', record_id=record_id)


@login_required
@role_required('doctor')
def dental_chart_delete_tooth(request, record_id, tooth_id):
    """Remove a tooth from the dental chart"""
    dental_record = get_object_or_404(DentalRecord, pk=record_id)
    tooth = get_object_or_404(DentalChart, pk=tooth_id, dental_record=dental_record)
    
    tooth_number = tooth.tooth_number
    tooth.delete()
    
    # If HTMX request, return the HTMX response template
    if request.headers.get('HX-Request'):
        teeth = DentalChart.objects.filter(dental_record=dental_record).prefetch_related('surfaces').order_by('tooth_number')
        
        # Build chart_data for JavaScript
        chart_data = {}
        for t in teeth:
            chart_data[str(t.tooth_number)] = {
                'id': t.id,
                'condition': t.condition,
                'notes': t.notes or '',
                'tooth_type': t.tooth_type,
            }
        
        response = render(request, 'dental_records/partials/dental_chart_htmx_response.html', {
            'dental_record': dental_record,
            'teeth': teeth,
            'chart_data': json.dumps(chart_data),
            'message': f'Tooth #{tooth_number} removed from chart.',
        })
        # Add HX-Trigger header to show message and update chart
        response['HX-Trigger'] = json.dumps({
            'showToothMessage': f'Tooth #{tooth_number} removed from chart.',
            'updateChartData': chart_data
        })
        return response
    
    # Only add messages for non-HTMX requests
    messages.success(request, f'Tooth #{tooth_number} removed from chart.')
    return redirect('dental_records:dental_record_edit', record_id=record_id)
