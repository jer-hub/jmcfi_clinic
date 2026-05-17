# JMCFI Clinic Management System

A web-based clinic management system built with Django for managing patient profiles, appointments, dental and medical records, document requests, pharmacy inventory, and clinic analytics.

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [System Requirements](#system-requirements)
- [Installation](#installation)
- [Running the Application](#running-the-application)
- [User Roles](#user-roles)
- [Application Modules](#application-modules)
- [Project Structure](#project-structure)
- [Configuration](#configuration)
- [Development](#development)
- [Support](#support)

---

## Overview

JMCFI Clinic is a Django application for clinic operations at an educational institution. It supports Google OAuth sign-in, role-based dashboards, appointment scheduling with month/week calendar views, medical and dental records, certificate/document requests, messaging, and admin analytics.

---

## Features

### Core
- Google OAuth authentication (domain-restricted)
- Role-based access: **patient**, staff, doctor, admin
- `PatientProfile` and `StaffProfile` with profile-completion enforcement
- Per-role session timeouts and clinic-wide settings
- HTMX-driven UI updates and Alpine.js for local interactivity

### Patients
- Demographics, emergency contacts, allergies, and institutional info
- Self-service appointment booking (when enabled for the patient role)
- Own medical/dental records and document requests

### Appointments
- Online scheduling and staff/doctor scheduling on behalf of patients
- Full-page and dashboard-embedded calendars (month and week views)
- Status workflow, doctor filters, ICS export
- Appointment type defaults and conflict checks

### Clinical records
- Medical records with prescriptions and walk-in create flow
- Dental records with charting and intake forms
- Health forms (profiles, dental forms, patient charts, prescriptions)

### Operations
- Document/certificate requests and processing
- Pharmacy inventory and dispensing
- Feedback and health tips
- Direct messaging and announcements
- Analytics dashboards and compliance reporting (admin/staff/doctor)

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Django 5.2, Channels 4.3 |
| Auth | django-allauth (Google OAuth) |
| Frontend | HTMX 1.9, Alpine.js 3.x, Tailwind CSS (CDN) |
| Database | SQLite (dev) / PostgreSQL (prod) |
| Package manager | [uv](https://github.com/astral-sh/uv) (`pyproject.toml`) |
| Static files | WhiteNoise |

---

## System Requirements

| Requirement | Version |
|-------------|---------|
| Python | 3.13+ (see `pyproject.toml`) |
| Django | 5.2 |
| Database | SQLite (default) or PostgreSQL |
| Browser | Modern Chromium, Firefox, Safari, or Edge |

**Recommended:** 4GB+ RAM, 1GB free disk space, internet for Google OAuth.

---

## Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/jer-hub/jmcfi_clinic.git
   cd jmcfi_clinic
   ```

2. **Install dependencies with uv** (recommended)
   ```bash
   uv sync
   ```

   Or with pip:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate   # Windows
   pip install -e .
   ```

3. **Environment variables** (create `.env` in the project root)
   ```env
   SECRET_KEY=your-secret-key
   DEBUG=True
   GOOGLE_CLIENT_ID=your-google-client-id
   GOOGLE_CLIENT_SECRET=your-google-client-secret
   GOOGLE_ALLOWED_DOMAINS=jmc.edu.ph,jmcfi.edu.ph
   ```

4. **Apply migrations**
   ```bash
   python manage.py migrate
   ```

5. **Optional: create a Django superuser**
   ```bash
   python manage.py createsuperuser
   ```

---

## Running the Application

```bash
python manage.py runserver
```

Open [http://127.0.0.1:8000/](http://127.0.0.1:8000/).

- **Django admin:** [http://127.0.0.1:8000/admin/](http://127.0.0.1:8000/admin/)
- **Dev admin login (local only):** [http://127.0.0.1:8000/auth/admin-login/](http://127.0.0.1:8000/auth/admin-login/) — see project Cursor rules for credentials

For WebSocket features (messaging), use an ASGI server compatible with Channels if required in your environment.

---

## User Roles

| Role | Typical access |
|------|----------------|
| **Patient** | Complete profile, book appointments, view own records, request documents, feedback, messaging |
| **Staff** | Clinic operations, appointments, records, document processing, analytics (per role settings) |
| **Doctor** | Appointments, clinical records, certificates, schedule-for-patient, patient search |
| **Admin** | User management, clinic/role settings, analytics; clinical namespaces can be blocked by policy |

Role constants and legacy compatibility live in `core/roles.py` (`student` in old data or decorators is normalized to `patient`).

---

## Application Modules

| App | URL prefix | Purpose |
|-----|------------|---------|
| `core/` | `/` | Dashboard, auth, profiles, notifications, user management, patient search |
| `appointments/` | `/appointments/` | Scheduling, calendar, appointment settings |
| `medical_records/` | `/medical-records/` | Medical history and prescriptions |
| `dental_records/` | `/dental-records/` | Dental exams and charting |
| `document_request/` | `/documents/` | Certificate/document requests |
| `feedback/` | `/feedback/` | Service feedback |
| `health_tips/` | `/health-tips/` | Articles and announcements |
| `health_forms_services/` | `/health-forms/` | Health/dental forms and charts |
| `analytics/` | `/analytics/` | Reporting and population health |
| `pharmacy/` | `/pharmacy/` | Inventory and dispensing |
| `messaging/` | `/messages/` | Direct messages and announcements |

---

## Project Structure

```
jmcfi_clinic/
├── backend/              # settings, root URLs, ASGI/WSGI
├── core/                 # User, PatientProfile, auth, dashboard, settings hub
├── appointments/
├── medical_records/
├── dental_records/
├── document_request/
├── feedback/
├── health_tips/
├── health_forms_services/
├── analytics/
├── pharmacy/
├── messaging/
├── templates/            # Shared components (calendar, modals, badges)
├── static/
├── media/
├── pyproject.toml        # Dependencies (use uv, not requirements.txt)
└── manage.py
```

---

## Configuration

| Area | Location |
|------|----------|
| Django settings | `backend/settings.py` |
| Clinic & role settings | Admin UI → Settings, or `ClinicSettings` / `RoleSettings` models |
| Profile required fields | `core/profile_policy.py` |
| Google OAuth | `.env` + `core/adapters.py` |

### Google OAuth

1. Create OAuth 2.0 credentials in [Google Cloud Console](https://console.cloud.google.com/).
2. Add authorized redirect URIs for your environment.
3. Set `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and `GOOGLE_ALLOWED_DOMAINS` in `.env`.

Patient Google signup profiling is described in `core/GOOGLE_STUDENT_PROFILE_POLICY.md` (patient-focused policy; filename retained).

---

## Development

```bash
# Run tests (example)
python manage.py test core.tests_roles appointments.tests_calendar

# System checks
python manage.py check
```

Key conventions are documented in `.cursor/rules/` (project structure, views, templates, auth).

After pulling changes that include migrations (e.g. student → patient rename), always run:

```bash
python manage.py migrate
```

---

## Support

| Document | Description |
|----------|-------------|
| `core/GOOGLE_STUDENT_PROFILE_POLICY.md` | Patient profile completion on Google signup |
| `appointments/APPOINTMENT_SCHEDULING_POLICY.md` | Scheduling rules |
| `document_request/DOCUMENT_REQUEST_POLICY.md` | Document request workflow |
| `core/ADMIN_ROLE_POLICY.md` | Admin access boundaries |

---

## Version History

**Current** — Patient role rename and calendar enhancements
- `student` role and `StudentProfile` renamed to **patient** / `PatientProfile` (DB migrations included)
- Unified dashboard calendar with month/week views for all roles
- Patient-first URLs and forms; legacy student aliases removed
- Role settings, clinic settings, and expanded test coverage

**1.0** — Initial release
- Core user management, appointments, dental/medical records, certificates, Google OAuth

---

## License

Proprietary to JMCFI Clinic. All rights reserved.

*© 2026 JMCFI Clinic Management System*
