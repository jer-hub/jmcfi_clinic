"""Progress notes API views."""

from datetime import datetime

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone

from core.decorators import role_required
from dental_records.models import DentalRecord, ProgressNote
from .helpers import _audit_dental


@login_required
@role_required('doctor', 'admin')
def progress_note_list(request, record_id):
    """Return all progress notes for a dental record as JSON."""
    dental_record = get_object_or_404(DentalRecord, pk=record_id)
    notes = dental_record.progress_notes.select_related('dentist').all()
    data = [
        {
            'id': n.id,
            'date': n.date.strftime('%Y-%m-%d'),
            'date_display': n.date.strftime('%b %d, %Y'),
            'procedure_done': n.procedure_done,
            'dentist': n.dentist.get_full_name() if n.dentist else '—',
            'remarks': n.remarks or '—',
        }
        for n in notes
    ]
    return JsonResponse({'notes': data})


@login_required
@role_required('doctor', 'admin')
def progress_note_create(request, record_id):
    """Create a progress note via JSON POST. Returns the new note."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required'}, status=405)

    dental_record = get_object_or_404(DentalRecord, pk=record_id)

    # Accept both form-encoded and JSON body
    if request.content_type and 'json' in request.content_type:
        import json as _json
        try:
            body = _json.loads(request.body)
        except _json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)
        date_val = body.get('date', '')
        procedure = body.get('procedure_done', '').strip()
        remarks = body.get('remarks', '').strip()
    else:
        date_val = request.POST.get('date', '')
        procedure = request.POST.get('procedure_done', '').strip()
        remarks = request.POST.get('remarks', '').strip()

    if not procedure:
        return JsonResponse({'success': False, 'error': 'Procedure done is required.'}, status=400)

    # Parse date string into a proper date object
    if date_val:
        try:
            parsed_date = datetime.strptime(date_val, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            parsed_date = timezone.now().date()
    else:
        parsed_date = timezone.now().date()

    note = ProgressNote.objects.create(
        dental_record=dental_record,
        date=parsed_date,
        procedure_done=procedure,
        dentist=request.user,
        remarks=remarks,
    )
    _audit_dental(
        request,
        dental_record,
        'edit',
        subresource='progress_note',
        operation='create',
    )
    return JsonResponse({
        'success': True,
        'note': {
            'id': note.id,
            'date': note.date.strftime('%Y-%m-%d'),
            'date_display': note.date.strftime('%b %d, %Y'),
            'procedure_done': note.procedure_done,
            'dentist': request.user.get_full_name(),
            'remarks': note.remarks or '—',
        }
    })


@login_required
@role_required('doctor', 'admin')
def progress_note_delete(request, record_id, note_id):
    """Delete a progress note. Returns JSON."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required'}, status=405)

    dental_record = get_object_or_404(DentalRecord, pk=record_id)
    note = get_object_or_404(ProgressNote, pk=note_id, dental_record=dental_record)
    _audit_dental(
        request,
        dental_record,
        'edit',
        subresource='progress_note',
        operation='delete',
    )
    note.delete()
    return JsonResponse({'success': True})
