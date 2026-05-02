# Admin Role & `is_staff` Dual-Gate System

## Overview

JMCFI Clinic has **two independent privilege dimensions** for admin users:

| Dimension | Set by | Controls |
|-----------|--------|----------|
| `role = 'admin'` | User model field | **App-level** access: user management, analytics, appointment settings, system notifications, messaging announcements |
| `is_staff = True` | Django flag | **Django Admin** (`/admin/`) access |
| `is_superuser = True` | Django flag | **Unrestricted** Django Admin (all models, all actions, bypasses `BlockAdminRoleMixin`) |

## Required Combinations

| User Type | `role` | `is_staff` | `is_superuser` | Django Admin | App Admin Views | Clinical Data (Django Admin) |
|-----------|--------|-----------|----------------|--------------|-----------------|------------------------------|
| Clinic Administrator | `admin` | `True` | `False` | Core, Appointments, Analytics, Messaging | Full access | Blocked (pharmacy, health forms, dental/medical records, feedback, document requests) |
| Superuser | `admin` | `True` | `True` | Everything | Full access | Full access |
| Clinical Staff | `staff`/`doctor` | `True` | `False` | Clinical apps only (if `is_staff=True`) | Limited (own appointments, health forms) | Full access |
| Student | `student` | `False` | `False` | None | Own data only | None |

## Why Two Gates?

1. **`role='admin'`** — Semantic role. Controls app-level views via `@admin_required` decorator. Used for user provisioning, system configuration, analytics.

2. **`is_staff`** — Django's built-in flag for Django Admin access. Controls who can access `/admin/`.

3. **`is_superuser`** — Django's built-in flag for unrestricted access. Bypasses all permission checks including `BlockAdminRoleMixin`.

## BlockAdminRoleMixin

Located in `core/admin_mixins.py`. Applied to all **clinical data** Django Admin registrations:
- `pharmacy` — Medicines, batches, suppliers, dispensing, stock adjustments
- `health_forms_services` — Health profile forms, dental forms, patient charts, prescriptions
- `health_tips` — Health tip content
- `feedback` — Student feedback and ratings
- `dental_records` — Dental examinations, charts, progress notes
- `medical_records` — Medical records and diagnoses
- `document_request` — Document requests, medical certificates, doctor signatures

**Not applied** to operational/admin apps:
- `core` — Users, profiles, notifications, invites, courses, departments
- `appointments` — Appointments and appointment type defaults
- `analytics` — Health trends, compliance reports, financial records
- `messaging` — Conversations, messages

## Admin Login

Admin users authenticate via `/auth/admin-login/` (dedicated endpoint), not the Google OAuth flow used by students/staff/doctors.

Security features:
- Brute-force protection: 5 attempts per 15 minutes (per IP+email)
- Security audit logging for all login attempts
- Shorter session timeout: 12 hours (vs 24 hours for other roles)
- Remember-me support with session expiry control

## Admin Profile Requirements

Admin users must complete their profile before accessing any service:
- `first_name`, `last_name` (on User model)
- `staff_id`, `phone` (on StaffProfile)

Enforced by `ProfileCompleteMiddleware` in `core/middleware.py`.

## Creating Admin Users

1. Create user with `role='admin'` via `POST /users/create/` (requires existing admin)
2. Set `is_staff=True` if Django Admin access needed
3. Set `is_superuser=True` only for unrestricted superuser access
4. Admin users receive invite links for account activation (same flow as other roles)

## Security Guards

- Admins **cannot** edit/delete/deactivate other admin accounts
- Admins **cannot** deactivate themselves
- Admins **cannot** reset passwords of other admin users
- All user provisioning actions are logged in `AccountProvisioningAudit`
