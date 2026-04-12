"""Appointment scheduling utility functions for interval-based conflict detection."""

from datetime import datetime, timedelta
from django.conf import settings
from django.db.models import Q
from .models import Appointment


def get_appointment_interval_minutes():
    """Get configured appointment buffer interval in minutes."""
    return getattr(settings, 'APPOINTMENT_INTERVAL_MINUTES', 30)


def get_time_conflict_query(date, time, interval_minutes=None):
    """
    Build time range query accounting for buffer interval.
    Returns Q object for conflicting time ranges.
    
    Args:
        date: DateField value
        time: TimeField (start time of proposed appointment)
        interval_minutes: Buffer interval (default from settings)
    
    Returns:
        Q object representing time range [time - interval, time + interval]
    """
    if interval_minutes is None:
        interval_minutes = get_appointment_interval_minutes()
    
    # Convert time to timedelta for calculation
    time_obj = datetime.combine(date, time)
    
    # Create buffer range: 30 min before to 30 min after
    start_buffer = time_obj - timedelta(minutes=interval_minutes)
    end_buffer = time_obj + timedelta(minutes=interval_minutes)
    
    # Adjust for date boundaries
    start_date = start_buffer.date()
    end_date = end_buffer.date()
    start_time = start_buffer.time()
    end_time = end_buffer.time()
    
    # Build query: time range that overlaps with [start_buffer, end_buffer]
    if start_date == end_date:
        # Same day buffer
        return Q(date=date, time__gte=start_time, time__lte=end_time)
    else:
        # Buffer spans midnight (rare but possible)
        return Q(
            Q(date=start_date, time__gte=start_time) |
            Q(date=end_date, time__lte=end_time)
        )


def get_conflicting_appointments(doctor, date, time, appointment_id=None, exclude_statuses=None):
    """
    Get list of appointments that conflict with proposed slot.
    Conflict = same doctor, overlapping time ± interval.
    
    Args:
        doctor: User object (doctor)
        date: DateField value (proposed date)
        time: TimeField (proposed time)
        appointment_id: Optional appointment ID to exclude (for edits)
        exclude_statuses: List of statuses to ignore (default: ['cancelled'])
    
    Returns:
        QuerySet of conflicting Appointment objects
    """
    if exclude_statuses is None:
        exclude_statuses = ['cancelled']
    
    interval_minutes = get_appointment_interval_minutes()
    
    # Get all non-cancelled, non-completed appointments for this doctor on this date
    conflicts = Appointment.objects.filter(
        doctor=doctor,
        date=date,
        status__in=['pending', 'confirmed'],  # Only active appointments block
    )
    
    # Exclude current appointment if updating
    if appointment_id:
        conflicts = conflicts.exclude(id=appointment_id)
    
    # Filter by time range with buffer
    time_query = get_time_conflict_query(date, time, interval_minutes)
    conflicts = conflicts.filter(time_query)
    
    return conflicts


def check_appointment_availability(doctor, date, time, appointment_id=None):
    """
    Check if time slot is available for doctor on date.
    
    Args:
        doctor: User object (doctor)
        date: DateField value
        time: TimeField
        appointment_id: Optional appointment ID to exclude (for edits)
    
    Returns:
        (is_available: bool, conflicts: QuerySet)
    """
    conflicts = get_conflicting_appointments(doctor, date, time, appointment_id)
    is_available = not conflicts.exists()
    return is_available, conflicts


def get_available_time_slots(doctor, date, start_hour=8, end_hour=17, slot_duration_minutes=30):
    """
    Get list of available time slots for doctor on date.
    
    Args:
        doctor: User object (doctor)
        date: DateField value
        start_hour: Start of business hours (default 8 AM)
        end_hour: End of business hours (default 5 PM)
        slot_duration_minutes: Slot size (default 30 min, same as interval)
    
    Returns:
        List of available times: [(HH:MM, label), ...]
    """
    interval = get_appointment_interval_minutes()
    available_slots = []
    
    # Generate all possible slots
    current = datetime.combine(date, datetime.min.time()).replace(hour=start_hour)
    end = datetime.combine(date, datetime.min.time()).replace(hour=end_hour)
    
    while current < end:
        is_available, _ = check_appointment_availability(doctor, date, current.time())
        if is_available:
            time_str = current.strftime('%H:%M')
            label = current.strftime('%I:%M %p')
            available_slots.append((time_str, label))
        
        current += timedelta(minutes=slot_duration_minutes)
    
    return available_slots


def format_conflict_message(doctor, conflicts):
    """
    Format user-friendly message for appointment conflicts.
    
    Args:
        doctor: User object (doctor)
        conflicts: QuerySet of conflicting appointments
    
    Returns:
        String message suitable for UI alert
    """
    if not conflicts.exists():
        return None
    
    conflict_appt = conflicts.first()
    doctor_name = f"{doctor.first_name} {doctor.last_name}".strip() or doctor.username
    conflict_time = conflict_appt.time.strftime('%I:%M %p')
    conflict_date = conflict_appt.date.strftime('%B %d, %Y')
    
    message = (
        f"This time slot is unavailable. Dr. {doctor_name} has an appointment "
        f"on {conflict_date} at {conflict_time}. "
        f"Please choose a different time or doctor."
    )
    return message
