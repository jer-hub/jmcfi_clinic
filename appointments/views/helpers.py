"""Shared private helpers for appointment views."""

from django.contrib.auth import get_user_model
import json

from appointments.models import AppointmentTypeDefault
from core.list_utils import is_json_request, paginate_queryset

User = get_user_model()

_is_json_request = is_json_request

# Re-export for local imports
__all__ = [
    '_get_schedule_context',
    '_is_json_request',
    '_validate_assigned_doctor_for_type',
    'paginate_queryset',
]


def _get_schedule_context(form_data=None, *, doctors_only=False):
    """
    Build doctor/type picker context for scheduling forms.
    When doctors_only is True, only users with role=doctor are included (staff booking).
    """
    active_defaults = (
        AppointmentTypeDefault.objects
        .filter(is_active=True)
        .prefetch_related('assigned_doctors')
        .order_by('appointment_type')
    )

    role_filter = ['doctor']

    type_doctor_map = {}
    all_assigned_ids = set()

    for default in active_defaults:
        assigned = list(
            default.assigned_doctors.filter(role__in=role_filter, is_active=True).values_list('id', flat=True)
        )
        type_doctor_map[default.appointment_type] = assigned
        all_assigned_ids.update(assigned)

    doctors = User.objects.filter(
        id__in=all_assigned_ids, role__in=role_filter, is_active=True
    ).select_related('staff_profile').order_by('first_name', 'last_name')

    doctors_payload = []
    for doctor in doctors:
        name = doctor.get_full_name() or doctor.email or ''
        spec = ''
        if getattr(doctor, 'staff_profile', None) and doctor.staff_profile.specialization:
            spec = f' - {doctor.staff_profile.specialization}'
        doctors_payload.append(
            {
                'id': str(doctor.id),
                'name': f'Dr. {name}{spec}',
            }
        )

    fd = form_data or {}
    return {
        'doctors': doctors,
        'doctors_json': json.dumps(doctors_payload),
        'active_defaults': active_defaults,
        'type_doctor_map': json.dumps(type_doctor_map),
        'form_data': fd,
        'form_data_json': json.dumps(fd),
    }


def _validate_assigned_doctor_for_type(doctor, appointment_type):
    """
    Return (is_valid, error_message) for doctor/type assignment.
    doctor must be a User instance; appointment_type is the choice key.
    """
    type_default = AppointmentTypeDefault.objects.filter(
        appointment_type=appointment_type, is_active=True
    ).prefetch_related('assigned_doctors').first()
    if not type_default:
        if AppointmentTypeDefault.objects.filter(appointment_type=appointment_type).exists():
            return False, 'This appointment type is currently inactive.'
        return False, 'Invalid appointment type selected.'

    allowed_ids = list(
        type_default.assigned_doctors.filter(
            role='doctor', is_active=True
        ).values_list('id', flat=True)
    )
    if not allowed_ids:
        return False, 'No doctors are available for this appointment type. Please contact the clinic.'
    if doctor.id not in allowed_ids:
        return False, 'The selected doctor is not available for this appointment type.'
    return True, ''
