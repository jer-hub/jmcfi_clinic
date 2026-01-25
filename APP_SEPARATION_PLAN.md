# Application Separation Plan

## Overview
Separating the monolithic `management` app into modular Django applications for better maintainability.

## New Application Structure

### 1. **appointments** - Appointment Management
- Models: `Appointment`, `AppointmentTypeDefault`
- Views: appointment_list, schedule_appointment, appointment_detail, appointment settings
- Forms: AppointmentForm, appointment defaults forms
- Templates: appointments/*

### 2. **medical_records** - Medical Records Management
- Models: `MedicalRecord`
- Views: medical_records, medical_record_detail, create_medical_record
- Templates: medical_records/*

### 3. **dental_records** - Dental Records Management
- Models: `DentalRecord`, `DentalExamination`, `DentalVitalSigns`, `DentalHealthQuestionnaire`, `DentalSystemsReview`, `DentalHistory`, `PediatricDentalHistory`, `DentalChart`
- Views: All dental-related views from views_dental.py
- Forms: All dental-related forms
- Templates: dental/*

### 4. **certificates** - Certificate Request Management
- Models: `CertificateRequest`
- Views: certificate_requests, request_certificate, process_certificate, view_certificate, print_certificate
- Templates: certificates/*

### 5. **feedback** - Feedback System
- Models: `Feedback`
- Views: feedback_list, submit_feedback
- Templates: feedback/*

### 6. **health_tips** - Health Tips Management
- Models: `HealthTip`
- Views: health_tips, create_health_tip, edit_health_tip, delete_health_tip, toggle_health_tip_status
- Templates: health_tips/*

### 7. **management** - Core User & Profile Management (Retained)
- Models: `User` (from core), `StudentProfile`, `StaffProfile`, `Notification`
- Views: dashboard, logout, notifications, user management
- Templates: base.html, dashboard, notifications, user management

## Implementation Strategy

### Phase 1: Keep Current Structure, Add New Apps (RECOMMENDED)
Instead of moving models immediately, we can:
1. Create new apps with their own logic
2. Keep models in `management` app temporarily
3. Import models from management in new apps
4. Gradually migrate data using Django migrations
5. This avoids breaking existing database

### Phase 2: URL Reorganization
- Create separate URL conf for each app
- Update main URLs to include new apps
- Keep backward compatibility with old URLs using redirects

### Phase 3: Template Reorganization  
- Move templates to respective app directories
- Update template references
- Keep shared templates in management/templates

## Risks & Considerations

1. **Database Migration Complexity**: Moving models between apps requires careful migration
2. **Foreign Key Relations**: Many models have FK relationships across domains
3. **Template Path Changes**: All template {% include %} and {% extends %} need updates
4. **URL Reversals**: All {% url %} tags need namespace updates
5. **Import Statements**: Every Python file importing models needs updates

## Alternative Recommendation

Instead of full app separation, consider:
- Keep all models in `management.models`
- Separate views into different view files (already done partially)
- Create logical URL namespaces
- Organize templates in subdirectories
- Use Django's `AppConfig` for better organization

This provides modular organization without migration complexity.

## Decision Required

**Option A**: Full separation (complex, requires careful migration)
**Option B**: Logical separation within management app (safer, easier)

Which approach would you prefer?
