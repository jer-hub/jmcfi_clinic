# Appointment Scheduling Policy

## Overview
This policy ensures clinic scheduling operates efficiently by preventing double-booking and maintaining adequate buffer time between consecutive appointments.

**NOTE:** This policy applies ONLY to appointments scheduled via the appointments app. Document requests are independent and use their own term-based scheduling (see document_request/DOCUMENT_REQUEST_POLICY.md).

## Key Rules

### 1. Time Slot Availability
- Appointments cannot be scheduled on weekends (Saturday-Sunday)
- Appointments cannot be scheduled for past dates
- Each appointment requires a 30-minute minimum interval between consecutive appointments with the same doctor
- No two appointments may share overlapping time windows (doctor-level)

### 2. Conflict Detection
**Conflict exists if:**
- Same doctor has another appointment on same date
- AND requested time overlaps with existing appointment ± 30-minute buffer
- Both appointments must have status in ['pending', 'confirmed', 'completed']

**Example:**
```
Doctor A scheduled: 10:00 AM - 11:00 AM
Blocked intervals (30 min buffer):
  - Too early: 09:30 AM - 10:30 AM
  - Too late:  10:30 AM - 11:30 AM
Available slots: 08:00 AM - 09:30 AM, 11:30 AM onwards
```

### 3. Status-Based Filtering
Conflicts are checked against appointments with status:
- `pending`: User may still cancel/reschedule
- `confirmed`: Definite conflict; block slot
- `completed`: Past appointment; do NOT block future slots

This prevents users from being blocked by old completed appointments.

### 4. Buffer Interval Details
- **Duration:** 30 minutes
- **When Applied:** Both before interval start and after interval end
- **Purpose:** Allow cleanup time, buffer for overruns, no back-to-back stress
- **Configuration:** Set via `APPOINTMENT_INTERVAL_MINUTES` in settings (default: 30)

### 5. User Alerts
When user selects a conflicted time slot:

**Alert Message Format:**
```
"This time slot is unavailable for Dr. [Doctor Name]. 
Dr. [Doctor Name] has an appointment on [Date] at [Time].
Try: [Suggested Available Times] or select a different doctor."
```

**Suggested Alternative Times:**
- Next available 30-min slot same day, same doctor
- If none: suggest next available day
- If doctor fully booked: suggest other available doctors

### 6. Edge Cases

#### Multiple Bookings for Same Student
Allowed. Student can have multiple appointments with different doctors on same day/time.
Example: 10:00 AM appointment with Dr. A + 10:00 AM appointment with Dr. B = OK

#### Doctor Availability
Check enforced ONLY against requested doctor.
If doctor unavailable, redirect to available doctor selection.

#### Cancellations
Cancelled appointments (`status='cancelled'`) do NOT block time slots.
Cancelled slot immediately becomes available.

#### Time Format
All times stored in 24-hour format (HH:MM).
API validates format; UI may display in 12-hour format with validation rules.

## Implementation

### Validation Function
```python
def check_appointment_availability(doctor, date, time, appointment_id=None, exclude_statuses=None):
    """Check if time slot available for doctor. Returns (is_available, conflicts)."""
```

### Configuration
Set in `backend/settings.py`:
```python
APPOINTMENT_INTERVAL_MINUTES = 30  # Adjust as needed (min: 15, max: 120)
```

## Testing Scenarios

1. **Exact time conflict:** Schedule at 10:00 AM when 10:00 AM exists → Block
2. **Buffer conflict (before):** Schedule at 09:50 AM (10 min before 10:00) → Block
3. **Buffer conflict (after):** Schedule at 10:50 AM (10 min after 11:00 end) → Block
4. **Just outside buffer:** Schedule at 09:29 AM (1 min before 30-min buffer) → Allow
5. **Completed appointment:** 10:00 AM completed; new 10:00 AM → Allow (no block on past)
6. **Different doctor:** Dr. A has 10:00; Dr. B at 10:00 on same date → Allow (per-doctor rule)
7. **Cancellation recovery:** Cancel 10:00 AM slot → 10:00 AM immediately available
