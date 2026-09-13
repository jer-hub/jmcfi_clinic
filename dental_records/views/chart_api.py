"""Interactive dental chart API views."""

import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from core.decorators import role_required
from dental_records.models import DentalChart, DentalChartSnapshot, DentalRecord, ToothSurface
from .helpers import _audit_dental, _is_json_request


@login_required
@role_required('doctor')
def dental_chart_api_get(request, record_id):
    """Get all teeth data for the dental chart as JSON"""
    dental_record = get_object_or_404(DentalRecord, pk=record_id)
    
    teeth = dental_record.dental_chart.all().prefetch_related('surfaces')
    
    teeth_data = []
    for tooth in teeth:
        surfaces_data = []
        for surface in tooth.surfaces.all():
            surfaces_data.append({
                'id': surface.id,
                'surface': surface.surface,
                'condition': surface.condition,
                'notes': surface.notes,
            })
        
        teeth_data.append({
            'id': tooth.id,
            'tooth_number': tooth.tooth_number,
            'tooth_type': tooth.tooth_type,
            'condition': tooth.condition,
            'notes': tooth.notes,
            'quadrant': tooth.fdi_quadrant,
            'quadrant_name': tooth.quadrant_name,
            'surfaces': surfaces_data,
        })
    
    return JsonResponse({
        'teeth': teeth_data,
        'record_id': record_id,
        'patient_name': dental_record.patient.get_full_name(),
    })


@login_required
@role_required('doctor')
def dental_chart_api_update_tooth(request, record_id):
    """Add or update a tooth in the dental chart via HTMX or AJAX"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
    
    dental_record = get_object_or_404(DentalRecord, pk=record_id)
    is_htmx = request.headers.get('HX-Request')
    
    # Parse data from either JSON or form data
    if _is_json_request(request):
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            if is_htmx:
                return render(request, 'dental_records/partials/dental_chart_message.html', {
                    'message': 'Invalid JSON data',
                    'message_type': 'error'
                })
            return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)
    else:
        data = request.POST
    
    tooth_number = data.get('tooth_number')
    tooth_type = data.get('tooth_type', 'permanent')
    condition = data.get('condition', 'healthy')
    notes = data.get('notes', '')
    
    if not tooth_number:
        if is_htmx:
            return render(request, 'dental_records/partials/dental_chart_message.html', {
                'message': 'Tooth number is required',
                'message_type': 'error'
            })
        return JsonResponse({'success': False, 'error': 'Tooth number is required'}, status=400)
    
    # Validate tooth number for FDI notation
    try:
        tooth_number = int(tooth_number)
        quadrant = tooth_number // 10
        position = tooth_number % 10
        
        # Permanent teeth: quadrants 1-4, positions 1-8
        # Primary teeth: quadrants 5-8, positions 1-5
        if quadrant in [1, 2, 3, 4]:
            if position < 1 or position > 8:
                error_msg = 'Invalid tooth position for permanent teeth (1-8)'
                if is_htmx:
                    return render(request, 'dental_records/partials/dental_chart_message.html', {
                        'message': error_msg,
                        'message_type': 'error'
                    })
                return JsonResponse({'success': False, 'error': error_msg}, status=400)
            tooth_type = 'permanent'
        elif quadrant in [5, 6, 7, 8]:
            if position < 1 or position > 5:
                error_msg = 'Invalid tooth position for primary teeth (1-5)'
                if is_htmx:
                    return render(request, 'dental_records/partials/dental_chart_message.html', {
                        'message': error_msg,
                        'message_type': 'error'
                    })
                return JsonResponse({'success': False, 'error': error_msg}, status=400)
            tooth_type = 'primary'
        else:
            error_msg = 'Invalid quadrant (1-4 for permanent, 5-8 for primary)'
            if is_htmx:
                return render(request, 'dental_records/partials/dental_chart_message.html', {
                    'message': error_msg,
                    'message_type': 'error'
                })
            return JsonResponse({'success': False, 'error': error_msg}, status=400)
    except (ValueError, TypeError):
        error_msg = 'Invalid tooth number format'
        if is_htmx:
            return render(request, 'dental_records/partials/dental_chart_message.html', {
                'message': error_msg,
                'message_type': 'error'
            })
        return JsonResponse({'success': False, 'error': error_msg}, status=400)
    
    # Create or update the tooth
    tooth, created = DentalChart.objects.update_or_create(
        dental_record=dental_record,
        tooth_number=tooth_number,
        defaults={
            'tooth_type': tooth_type,
            'condition': condition,
            'notes': notes,
        }
    )
    
    # Handle surface conditions if provided
    surfaces = ['mesial', 'distal', 'buccal', 'lingual', 'occlusal']
    for surface_name in surfaces:
        surface_value = data.get(f'surface_{surface_name}')
        if surface_value:
            ToothSurface.objects.update_or_create(
                tooth=tooth,
                surface=surface_name,
                defaults={'condition': surface_value}
            )
        else:
            # Remove surface if not set
            ToothSurface.objects.filter(tooth=tooth, surface=surface_name).delete()
    
    _audit_dental(
        request,
        dental_record,
        'edit',
        subresource='dental_chart',
        operation='update_tooth',
    )
    
    # Return HTMX response with updated table and chart data
    if is_htmx:
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
            'message': f'Tooth #{tooth_number} {"added" if created else "updated"} successfully!',
        })
        # Add HX-Trigger header to close modal and show message
        response['HX-Trigger'] = json.dumps({
            'closeToothModal': True,
            'showToothMessage': f'Tooth #{tooth_number} {"added" if created else "updated"} successfully!',
            'updateChartData': chart_data
        })
        return response
    
    return JsonResponse({
        'success': True,
        'created': created,
        'tooth': {
            'id': tooth.id,
            'tooth_number': tooth.tooth_number,
            'tooth_type': tooth.tooth_type,
            'condition': tooth.condition,
            'notes': tooth.notes,
            'quadrant': tooth.fdi_quadrant,
            'quadrant_name': tooth.quadrant_name,
        }
    })


@login_required
@role_required('doctor')
def dental_chart_api_delete_tooth(request, record_id, tooth_id):
    """Delete a tooth from the dental chart via HTMX or AJAX (supports DELETE method)"""
    dental_record = get_object_or_404(DentalRecord, pk=record_id)
    tooth = get_object_or_404(DentalChart, pk=tooth_id, dental_record=dental_record)
    is_htmx = request.headers.get('HX-Request')
    
    tooth_number = tooth.tooth_number
    _audit_dental(
        request,
        dental_record,
        'edit',
        subresource='dental_chart',
        operation='delete_tooth',
    )
    tooth.delete()
    
    if is_htmx:
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
            'message': f'Tooth #{tooth_number} deleted successfully.',
        })
        # Add HX-Trigger header to show message and update chart
        response['HX-Trigger'] = json.dumps({
            'showToothMessage': f'Tooth #{tooth_number} deleted successfully.',
            'updateChartData': chart_data
        })
        return response
    
    return JsonResponse({
        'success': True,
        'message': f'Tooth #{tooth_number} deleted successfully.'
    })


@login_required
@role_required('doctor')
def dental_chart_api_update_surface(request, record_id, tooth_id):
    """Update surface condition for a specific tooth"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
    
    dental_record = get_object_or_404(DentalRecord, pk=record_id)
    tooth = get_object_or_404(DentalChart, pk=tooth_id, dental_record=dental_record)
    
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)
    
    surface_name = data.get('surface')
    condition = data.get('condition', 'healthy')
    notes = data.get('notes', '')
    
    if not surface_name:
        return JsonResponse({'success': False, 'error': 'Surface name is required'}, status=400)
    
    valid_surfaces = ['mesial', 'distal', 'buccal', 'lingual', 'occlusal', 'incisal']
    if surface_name not in valid_surfaces:
        return JsonResponse({'success': False, 'error': f'Invalid surface. Must be one of: {", ".join(valid_surfaces)}'}, status=400)
    
    # Create or update the surface
    surface, created = ToothSurface.objects.update_or_create(
        tooth=tooth,
        surface=surface_name,
        defaults={
            'condition': condition,
            'notes': notes,
        }
    )
    
    _audit_dental(
        request,
        dental_record,
        'edit',
        subresource='dental_chart',
        operation='update_surface',
    )
    
    return JsonResponse({
        'success': True,
        'created': created,
        'surface': {
            'id': surface.id,
            'surface': surface.surface,
            'condition': surface.condition,
            'notes': surface.notes,
        }
    })


@login_required
@role_required('doctor')
def dental_chart_api_delete_surface(request, record_id, tooth_id, surface_id):
    """Delete a surface marking from a tooth"""
    if request.method != 'DELETE':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
    
    dental_record = get_object_or_404(DentalRecord, pk=record_id)
    tooth = get_object_or_404(DentalChart, pk=tooth_id, dental_record=dental_record)
    surface = get_object_or_404(ToothSurface, pk=surface_id, tooth=tooth)
    
    _audit_dental(
        request,
        dental_record,
        'edit',
        subresource='dental_chart',
        operation='delete_surface',
    )
    surface.delete()
    
    return JsonResponse({'success': True})


@login_required
@role_required('doctor')
def dental_chart_api_bulk_update(request, record_id):
    """Bulk update multiple teeth at once (for multi-select feature)"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
    
    dental_record = get_object_or_404(DentalRecord, pk=record_id)
    is_htmx = request.headers.get('HX-Request')
    
    # Parse data from either JSON or form data
    if _is_json_request(request):
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            if is_htmx:
                return render(request, 'dental_records/partials/dental_chart_message.html', {
                    'message': 'Invalid JSON data',
                    'message_type': 'error'
                })
            return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)
        tooth_numbers = data.get('tooth_numbers', [])
        condition = data.get('condition', 'healthy')
        notes = data.get('notes', '')
    else:
        # Form data - tooth_numbers_json is a JSON string of selected teeth
        tooth_numbers_json = request.POST.get('tooth_numbers_json', '[]')
        try:
            tooth_numbers = json.loads(tooth_numbers_json)
        except json.JSONDecodeError:
            tooth_numbers = []
        condition = request.POST.get('condition', 'healthy')
        notes = request.POST.get('notes', '')
    
    if not tooth_numbers:
        if is_htmx:
            return render(request, 'dental_records/partials/dental_chart_message.html', {
                'message': 'No teeth selected',
                'message_type': 'error'
            })
        return JsonResponse({'success': False, 'error': 'No teeth selected'}, status=400)
    
    updated_teeth = []
    errors = []
    
    for tooth_number in tooth_numbers:
        try:
            tooth_number = int(tooth_number)
            quadrant = tooth_number // 10
            position = tooth_number % 10
            
            # Determine tooth type
            if quadrant in [1, 2, 3, 4]:
                if position < 1 or position > 8:
                    errors.append(f'Invalid position for tooth {tooth_number}')
                    continue
                tooth_type = 'permanent'
            elif quadrant in [5, 6, 7, 8]:
                if position < 1 or position > 5:
                    errors.append(f'Invalid position for tooth {tooth_number}')
                    continue
                tooth_type = 'primary'
            else:
                errors.append(f'Invalid quadrant for tooth {tooth_number}')
                continue
            
            tooth, _ = DentalChart.objects.update_or_create(
                dental_record=dental_record,
                tooth_number=tooth_number,
                defaults={
                    'tooth_type': tooth_type,
                    'condition': condition,
                    'notes': notes,
                }
            )
            updated_teeth.append(tooth_number)
        except (ValueError, TypeError):
            errors.append(f'Invalid tooth number: {tooth_number}')
    
    if updated_teeth:
        _audit_dental(
            request,
            dental_record,
            'edit',
            subresource='dental_chart',
            operation='bulk_update',
        )
    
    if is_htmx:
        # Return HTMX response with updated teeth table and chart data
        teeth = DentalChart.objects.filter(dental_record=dental_record).order_by('tooth_number')
        
        # Build chart_data for JavaScript
        chart_data = {}
        for tooth in teeth:
            chart_data[str(tooth.tooth_number)] = {
                'id': tooth.id,
                'condition': tooth.condition,
                'notes': tooth.notes or '',
                'tooth_type': tooth.tooth_type,
            }
        
        response = render(request, 'dental_records/partials/dental_chart_htmx_response.html', {
            'dental_record': dental_record,
            'teeth': teeth,
            'chart_data': json.dumps(chart_data),
            'message': f'Successfully updated {len(updated_teeth)} teeth',
        })
        # Add HX-Trigger header to close modal and show message
        response['HX-Trigger'] = json.dumps({
            'closeBulkModal': True,
            'showToothMessage': f'Successfully updated {len(updated_teeth)} teeth',
            'updateChartData': chart_data
        })
        return response
    
    return JsonResponse({
        'success': True,
        'updated_count': len(updated_teeth),
        'updated_teeth': updated_teeth,
        'errors': errors,
    })


@login_required
@role_required('doctor')
def dental_chart_api_save_snapshot(request, record_id):
    """Save a snapshot of the current dental chart for comparison"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
    
    dental_record = get_object_or_404(DentalRecord, pk=record_id)
    
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        data = {}
    
    notes = data.get('notes', '')
    
    # Build snapshot data
    teeth = dental_record.dental_chart.all().prefetch_related('surfaces')
    chart_data = []
    
    for tooth in teeth:
        tooth_data = {
            'tooth_number': tooth.tooth_number,
            'tooth_type': tooth.tooth_type,
            'condition': tooth.condition,
            'notes': tooth.notes,
            'surfaces': []
        }
        for surface in tooth.surfaces.all():
            tooth_data['surfaces'].append({
                'surface': surface.surface,
                'condition': surface.condition,
                'notes': surface.notes,
            })
        chart_data.append(tooth_data)
    
    # Create snapshot
    snapshot = DentalChartSnapshot.objects.create(
        dental_record=dental_record,
        notes=notes,
        chart_data=chart_data,
        created_by=request.user,
    )
    
    _audit_dental(
        request,
        dental_record,
        'edit',
        subresource='dental_chart',
        operation='save_snapshot',
    )
    
    return JsonResponse({
        'success': True,
        'snapshot_id': snapshot.id,
        'snapshot_date': snapshot.snapshot_date.isoformat(),
    })


@login_required
@role_required('doctor')
def dental_chart_api_get_snapshots(request, record_id):
    """Get list of all snapshots for a dental record"""
    dental_record = get_object_or_404(DentalRecord, pk=record_id)
    
    snapshots = dental_record.chart_snapshots.all()
    
    snapshots_data = []
    for snapshot in snapshots:
        snapshots_data.append({
            'id': snapshot.id,
            'date': snapshot.snapshot_date.isoformat(),
            'notes': snapshot.notes,
            'created_by': snapshot.created_by.get_full_name() if snapshot.created_by else 'Unknown',
            'teeth_count': len(snapshot.chart_data) if snapshot.chart_data else 0,
        })
    
    return JsonResponse({'snapshots': snapshots_data})


@login_required
@role_required('doctor')
def dental_chart_api_get_snapshot(request, record_id, snapshot_id):
    """Get a specific snapshot's data for comparison"""
    dental_record = get_object_or_404(DentalRecord, pk=record_id)
    snapshot = get_object_or_404(DentalChartSnapshot, pk=snapshot_id, dental_record=dental_record)
    
    return JsonResponse({
        'id': snapshot.id,
        'date': snapshot.snapshot_date.isoformat(),
        'notes': snapshot.notes,
        'created_by': snapshot.created_by.get_full_name() if snapshot.created_by else 'Unknown',
        'chart_data': snapshot.chart_data,
    })


@login_required
@role_required('doctor')
def dental_chart_api_compare_snapshots(request, record_id):
    """Compare two snapshots to see changes over time"""
    dental_record = get_object_or_404(DentalRecord, pk=record_id)
    
    snapshot1_id = request.GET.get('snapshot1')
    snapshot2_id = request.GET.get('snapshot2')
    
    if not snapshot1_id or not snapshot2_id:
        return JsonResponse({'success': False, 'error': 'Both snapshot IDs are required'}, status=400)
    
    snapshot1 = get_object_or_404(DentalChartSnapshot, pk=snapshot1_id, dental_record=dental_record)
    snapshot2 = get_object_or_404(DentalChartSnapshot, pk=snapshot2_id, dental_record=dental_record)
    
    # Build comparison data
    teeth1 = {t['tooth_number']: t for t in snapshot1.chart_data or []}
    teeth2 = {t['tooth_number']: t for t in snapshot2.chart_data or []}
    
    all_teeth = set(teeth1.keys()) | set(teeth2.keys())
    
    changes = []
    for tooth_num in sorted(all_teeth):
        tooth1 = teeth1.get(tooth_num)
        tooth2 = teeth2.get(tooth_num)
        
        if tooth1 and tooth2:
            if tooth1['condition'] != tooth2['condition']:
                changes.append({
                    'tooth_number': tooth_num,
                    'type': 'condition_changed',
                    'from': tooth1['condition'],
                    'to': tooth2['condition'],
                })
        elif tooth1 and not tooth2:
            changes.append({
                'tooth_number': tooth_num,
                'type': 'removed',
                'condition': tooth1['condition'],
            })
        elif not tooth1 and tooth2:
            changes.append({
                'tooth_number': tooth_num,
                'type': 'added',
                'condition': tooth2['condition'],
            })
    
    return JsonResponse({
        'snapshot1': {
            'id': snapshot1.id,
            'date': snapshot1.snapshot_date.isoformat(),
        },
        'snapshot2': {
            'id': snapshot2.id,
            'date': snapshot2.snapshot_date.isoformat(),
        },
        'changes': changes,
        'total_changes': len(changes),
    })


@login_required
@role_required('doctor')
def dental_chart_api_export(request, record_id):
    """Export the dental chart data as JSON"""
    dental_record = get_object_or_404(DentalRecord, pk=record_id)
    
    _audit_dental(request, dental_record, 'export', format='json', subresource='dental_chart')
    
    teeth = dental_record.dental_chart.all().prefetch_related('surfaces')
    
    export_data = {
        'record_id': record_id,
        'patient_name': dental_record.patient.get_full_name(),
        'examination_date': dental_record.date_of_examination.isoformat() if dental_record.date_of_examination else None,
        'exported_at': timezone.now().isoformat(),
        'teeth': []
    }
    
    for tooth in teeth:
        tooth_data = {
            'tooth_number': tooth.tooth_number,
            'fdi_notation': f"Q{tooth.fdi_quadrant}-{tooth.fdi_tooth_position}",
            'quadrant_name': tooth.quadrant_name,
            'tooth_type': tooth.tooth_type,
            'condition': tooth.condition,
            'condition_display': tooth.get_condition_display(),
            'notes': tooth.notes,
            'surfaces': []
        }
        
        for surface in tooth.surfaces.all():
            tooth_data['surfaces'].append({
                'surface': surface.surface,
                'surface_display': surface.get_surface_display(),
                'condition': surface.condition,
                'condition_display': surface.get_condition_display(),
                'notes': surface.notes,
            })
        
        export_data['teeth'].append(tooth_data)
    
    return JsonResponse(export_data, json_dumps_params={'indent': 2})
