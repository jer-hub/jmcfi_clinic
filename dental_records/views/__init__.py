"""Dental records views — re-exported for urls.py compatibility."""

from dental_records.views.chart_api import (
    dental_chart_api_bulk_update,
    dental_chart_api_compare_snapshots,
    dental_chart_api_delete_surface,
    dental_chart_api_delete_tooth,
    dental_chart_api_export,
    dental_chart_api_get,
    dental_chart_api_get_snapshot,
    dental_chart_api_get_snapshots,
    dental_chart_api_save_snapshot,
    dental_chart_api_update_surface,
    dental_chart_api_update_tooth,
)
from dental_records.views.chart_page import dental_chart_add_tooth, dental_chart_delete_tooth
from dental_records.views.crud import (
    dental_record_create,
    dental_record_delete,
    dental_record_detail,
    dental_record_edit,
)
from dental_records.views.export import dental_record_export_json
from dental_records.views.intake import (
    resend_guest_intake_link,
    send_guest_intake_link,
    student_dental_intake,
)
from dental_records.views.list import dental_record_list
from dental_records.views.patients_api import get_patient_profile, search_patients
from dental_records.views.progress_notes import (
    progress_note_create,
    progress_note_delete,
    progress_note_list,
)
from dental_records.views.status import (
    complete_appointment,
    dental_record_status_modal,
    mark_record_completed,
)

__all__ = [
    'complete_appointment',
    'dental_chart_add_tooth',
    'dental_chart_api_bulk_update',
    'dental_chart_api_compare_snapshots',
    'dental_chart_api_delete_surface',
    'dental_chart_api_delete_tooth',
    'dental_chart_api_export',
    'dental_chart_api_get',
    'dental_chart_api_get_snapshot',
    'dental_chart_api_get_snapshots',
    'dental_chart_api_save_snapshot',
    'dental_chart_api_update_surface',
    'dental_chart_api_update_tooth',
    'dental_chart_delete_tooth',
    'dental_record_create',
    'dental_record_delete',
    'dental_record_detail',
    'dental_record_edit',
    'dental_record_export_json',
    'dental_record_list',
    'dental_record_status_modal',
    'get_patient_profile',
    'mark_record_completed',
    'progress_note_create',
    'progress_note_delete',
    'progress_note_list',
    'resend_guest_intake_link',
    'search_patients',
    'send_guest_intake_link',
    'student_dental_intake',
]
