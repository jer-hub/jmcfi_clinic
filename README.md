# JMCFI Clinic Management System

A comprehensive web-based clinic management system built with Django for managing patient records, appointments, dental records, and medical services.

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [System Requirements](#system-requirements)
- [Installation](#installation)
- [Running the Application](#running-the-application)
- [User Roles](#user-roles)
- [Application Modules](#application-modules)
- [Project Structure](#project-structure)
- [Configuration](#configuration)
- [Support](#support)

---

## Overview

JMCFI Clinic Management System is a Django-based web application designed to streamline clinic operations for educational institutions. It provides tools for managing patient profiles, scheduling appointments, maintaining dental and medical records, and generating health certificates.

---

## Features

### Core Features
- User authentication with Google OAuth integration
- Role-based access control (Student, Staff, Doctor, Admin)
- Profile management with comprehensive demographics
- Session timeout for security

### Patient Management
- Student and Staff profile management
- Medical history tracking
- Emergency contact information
- Allergy and medical condition records

### Appointment System
- Online appointment scheduling
- Appointment status tracking
- Doctor availability management
- Appointment reminders

### Dental Records
- Complete dental examination records
- Vital signs tracking
- Health questionnaire management
- Systems review documentation
- Dental chart and treatment history

### Medical Records
- Patient medical history
- Treatment records
- Prescription management

### Additional Features
- Health certificates generation
- Patient feedback system
- Health tips and announcements
- Responsive design (mobile-friendly)

---

## System Requirements

| Requirement | Version |
|-------------|---------|
| Python | 3.10 or higher |
| Django | 4.x or higher |
| Database | SQLite (default) or PostgreSQL |
| Browser | Chrome, Firefox, Edge, Safari |

**Recommended:**
- 4GB RAM minimum
- 1GB free disk space
- Internet connection (for Google OAuth)

---

## Installation

1. **Clone or download the project**
   ```bash
   git clone <repository-url>
   cd jmcfi_clinic
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   ```

3. **Activate the virtual environment**
   ```bash
   # Windows
   venv\Scripts\activate
   
   # Linux/Mac
   source venv/bin/activate
   ```

4. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   
   # Or if using uv
   uv pip install -r requirements.txt
   ```

5. **Configure environment variables** (create `.env` file)
   ```env
   SECRET_KEY=your-secret-key
   DEBUG=True
   GOOGLE_CLIENT_ID=your-google-client-id
   GOOGLE_CLIENT_SECRET=your-google-client-secret
   ```

6. **Run database migrations**
   ```bash
   python manage.py migrate
   ```

7. **Create a superuser account**
   ```bash
   python manage.py createsuperuser
   ```

---

## Running the Application

### Development Server

1. Activate your virtual environment
2. Run the development server:
   ```bash
   python manage.py runserver
   ```
3. Open your browser and navigate to: `http://127.0.0.1:8000/`

### Admin Panel
Access the admin panel at: `http://127.0.0.1:8000/admin/`

---

## User Roles

| Role | Permissions |
|------|-------------|
| **Student** | View/edit personal profile, book appointments, view own records, submit feedback |
| **Staff** | View/edit personal profile, book appointments, view own records, submit feedback |
| **Doctor** | Manage appointments, create/update medical & dental records, issue certificates, view patient history |
| **Admin** | Full system access, user management, system configuration, report generation |

---

## Application Modules

### Core (`/core/`)
- Custom user model with role support
- Authentication adapters
- Middleware (session timeout)
- Base templates and utilities

### Management (`/management/`)
- Dashboard views
- User profile management
- Appointment management
- User administration
- System settings

### Appointments (`/appointments/`)
- Appointment scheduling
- Calendar views
- Status management

### Dental Records (`/dental_records/`)
- Dental examination records
- Vital signs tracking
- Health questionnaire
- Systems review
- Treatment history

### Medical Records (`/medical_records/`)
- Patient medical history
- Treatment documentation

### Certificates (`/certificates/`)
- Health certificate generation
- Certificate templates

### Feedback (`/feedback/`)
- Patient feedback collection
- Feedback management

### Health Tips (`/health_tips/`)
- Health announcements
- Tips and reminders

---

## Project Structure

```
jmcfi_clinic/
├── backend/                 # Main Django settings
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── core/                    # Core app (users, auth)
│   ├── models.py
│   ├── views.py
│   └── middleware.py
├── management/              # Main management app
│   ├── models.py
│   ├── views.py
│   ├── forms.py
│   └── templates/
├── appointments/            # Appointments module
├── dental_records/          # Dental records module
├── medical_records/         # Medical records module
├── certificates/            # Certificates module
├── feedback/                # Feedback module
├── health_tips/             # Health tips module
├── templates/               # Global templates
├── staticfiles/             # Static files
├── media/                   # User uploads
├── manage.py
└── db.sqlite3               # SQLite database
```

---

## Configuration

### Key Settings (`backend/settings.py`)

| Setting | Description |
|---------|-------------|
| `DEBUG` | Set to `False` in production |
| `ALLOWED_HOSTS` | Configure for production domain |
| `DATABASE` | SQLite by default, can be changed to PostgreSQL |
| `SESSION_COOKIE_AGE` | Session timeout duration |

### Google OAuth Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create OAuth 2.0 credentials
3. Add authorized redirect URIs
4. Update `.env` with credentials

See `GOOGLE_OAUTH_GUIDE.md` for detailed instructions.

---

## Support

### Documentation Files

| File | Description |
|------|-------------|
| `DEPLOYMENT_CHECKLIST.md` | Production setup guide |
| `SESSION_TIMEOUT_GUIDE.md` | Security settings |
| `DENTAL_RECORDS_QUICK_START.md` | Dental module usage |
| `GOOGLE_OAUTH_GUIDE.md` | OAuth configuration |
| `APP_STRUCTURE_STATUS.md` | Application structure |

---

## Version History

**Version 1.0** - Initial Release
- Core user management
- Appointment scheduling
- Dental records module
- Medical records module
- Certificate generation
- Google OAuth integration
- Session timeout security

---

## License

This software is proprietary to JMCFI Clinic. All rights reserved.

---

*© 2026 JMCFI Clinic Management System*
