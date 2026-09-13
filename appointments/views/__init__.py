"""Appointments views — re-exported for urls.py compatibility."""

from appointments.views.calendar import (
    appointment_calendar,
    calendar_body_fragment,
    calendar_day_fragment,
    calendar_export_ics,
    calendar_month_fragment,
)
from appointments.views.detail import appointment_detail
from appointments.views.helpers import _get_schedule_context
from appointments.views.list import appointment_list
from appointments.views.schedule import appointment_slot_availability, schedule_appointment
from appointments.views.schedule_for_patient import schedule_for_patient
from appointments.views.settings import (
    appointment_type_settings,
    edit_appointment_type_default,
    toggle_appointment_type_default,
)

__all__ = [
    '_get_schedule_context',
    'appointment_calendar',
    'appointment_detail',
    'appointment_list',
    'appointment_slot_availability',
    'appointment_type_settings',
    'calendar_body_fragment',
    'calendar_day_fragment',
    'calendar_export_ics',
    'calendar_month_fragment',
    'edit_appointment_type_default',
    'schedule_appointment',
    'schedule_for_patient',
    'toggle_appointment_type_default',
]
