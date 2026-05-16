# Document Request Policy

## Overview
Students and doctors request documents (medical certificates and records) through simple form submission. Document requests operate independently from both appointments and any scheduling windows. Any student can request documents at any time without restrictions.

## Key Rules

### 1. No Schedule Requirement
Students can submit document requests anytime without schedule window restrictions:
- No daily time window validation
- No allowed days restriction
- No StudentRequestSchedule requirement
- Doctor, staff, or admin can initiate requests on behalf of students

### 2. Document Types
Only `medical_certificate` supported for requests.
- Form locked to medical_certificate choice
- Backend validation rejects other types
- Historical data may contain other types but new requests blocked

### 3. Request Workflow - Student Path
1. Student submits document request form anytime (no schedule restriction)
2. System auto-generates MedicalCertificate record (drafted)
3. Doctor reviews and signs certificate
4. Certificate sent to student

**Request States (DocumentRequest — single source of truth):**
- `pending_review`: Awaiting clinician review/signature
- `ready_for_pickup`: Approved; certificate issued
- `rejected`: Rejected with reason

**Certificate States (MedicalCertificate):**
- `draft`: Editable while request is under review
- `issued`: Signed and approved
- `void`: Request was rejected

### 4. Request Workflow - Doctor Path (Doctor-Initiated)
1. Doctor directly creates request on behalf of student
2. Auto-populates certificate fields from doctor's records
3. Doctor signs immediately (optional)
4. Request marked `completed` or `pending` awaiting student

### 5. No Appointment or Schedule Requirement
- Document requests work independently from appointments app
- No schedule window validation
- Students can request anytime, any number of times
- No StudentRequestSchedule requirement
- Appointment system operates separately (see APPOINTMENT_SCHEDULING_POLICY.md)

### 6. Access Control by Role

**Student:**
- Can view own requests only
- Can request anytime (no schedule restriction)
- Cannot directly sign certificates
- Only one **pending_review** request per document type at a time (additional requests allowed after ready_for_pickup/rejection)

**Doctor / Staff:**
- Can view all requests
- Can request on behalf of students anytime
- Can complete or reject certificates (must upload signature before completing)
- Can view request details and student info

**Admin:**
- Can view all requests and process complete/reject flows
- Must upload a signature before completing requests (same as doctor/staff)

### 7. Notification Flow

**When student requests:**
→ Notification sent to the **assigned doctor** (see resolution order below)

**Assigned doctor resolution:**
1. Clinician on the student's most recent non-cancelled appointment
2. Otherwise, clinician(s) assigned to the active `consultation` appointment type default (all assigned if multiple)
3. If none configured, no automatic notification is sent (logged server-side)

**When doctor signs:**
→ Notification sent to student

**When doctor rejects:**
→ Notification includes rejection reason

### 8. Edge Cases

#### Multiple Requests Same Term
- Allowed after a prior request is completed or rejected
- Only one pending medical certificate request per student at a time

#### Clinician Signature Requirements
- Doctors and staff must upload a signature image on the **My Signature** page (`/documents/signature/`)
- Cannot complete a request without an on-file signature
- Completion copies the signature to the certificate snapshot and records `signed_by` / `signed_at`

#### Expired Certificates
- Certificates valid per clinic policy (external to this system)
- No auto-expiration in system; admin manually archives if needed

## Implementation

### Model Structure
```
DocumentRequest
  - student (FK to User, role='student')
  - document_type (choices: [medical_certificate only])
  - status (pending_review | ready_for_pickup | rejected)
  - assigned_to (FK — clinician notified at create)
  - rejection_reason (optional)
  - created_by (FK to User, for audit trail)
  - request_origin (student | doctor | admin)
  
MedicalCertificate (auto-created from DocumentRequest)
  - student (FK)
  - document_request (FK)
  - physician_name
  - consultation_date
  - diagnosis
  - remarks
  - status (draft | issued | void)
  - issued_pdf (cached on approve)
  - signature (ClinicianSignature snapshot)

Workflow commands live in `document_request/services/` (`approve_request`, `reject_request`, `save_certificate_draft`). Status is **not** synced via signals.
```

### Validation Points
```python
# In request_document view:
# Only validate document type, no schedule window validation

DocumentRequest.clean()  # Validates document_type in ALLOWED
```

### Configuration
```python
# settings.py
ALLOWED_DOCUMENT_TYPES = [
    ('medical_certificate', 'Medical Certificate'),
]
```

## Testing Scenarios

1. **Anytime request:** Student submits any time → Allow
2. **Multiple requests:** Same student, multiple times → Allow
3. **Doctor-initiated:** Doctor creates on behalf → Allow
4. **Different types:** Student requests different certificate types → Only medical_cert allowed
5. **Student views own:** Student sees only own requests → Correct
6. **Doctor views all:** Doctor sees all requests → Correct
7. **Missing signature:** Doctor signs without image on file → Reject
8. **Status progression:** pending → completed → downloadable → Correct
9. **Rejection with reason:** Doctor rejects; student sees reason → Correct
10. **No approval needed:** Request auto-creates certificate (no schedule gating) → Correct

## Relationship to Appointments

**APPOINTMENTS** (separate app):
- Doctors hold appointment time slots
- Students book appointments with doctors
- Uses 30-min interval buffer policy
- Status: pending, confirmed, completed, cancelled

**DOCUMENT REQUESTS** (this policy):
- Students request documents anytime (no schedule requirement)
- Requests are independent of specific appointments
- Doctors review and sign certificates
- Status: pending, completed, rejected
- NO automatic link or dependency on appointments
- NO schedule window validation

Students CAN request documents without ever booking an appointment.
Appointments CAN exist without any document requests.
Both systems operate independently with no temporal coupling.
