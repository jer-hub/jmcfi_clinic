# Google Student Signup Profiling Policy

## Purpose
Require student users who sign up using Google OAuth to complete profile fields before accessing clinic services.

## Trigger
- Applies to Google social signup/login users with role `student`.
- Enforcement starts immediately after authentication.

## Required Student Profile Fields
- student_id
- middle_name
- gender
- civil_status
- date_of_birth
- place_of_birth
- age
- address
- phone
- emergency_contact
- emergency_phone
- department
- blood_type

Optional:
- telephone_number

## Enforcement Points
1. `core.middleware.ProfileCompleteMiddleware`
   - Blocks access to non-exempt pages when profile is incomplete.
   - Redirects to `core:profile_required`.

2. `core.decorators.profile_required`
   - Protects decorated views with same completeness policy.

3. `core.adapters.GoogleOnlyAdapter`
   - On new Google student signup, sends policy message reminding user to complete profile.

4. `core.utils`
   - Uses centralized policy constants for completion and missing-field checks.

## Source of Truth
- `core/profile_policy.py`
  - `STUDENT_PROFILE_REQUIRED_FIELDS`
  - `STAFF_PROFILE_REQUIRED_FIELDS`

All profile-completion checks must use these constants to avoid policy drift.
