# Google OAuth Profile Data Integration

## Overview
This system automatically captures user data from Google OAuth and populates user profiles in the JMCFI Clinic system.

## Data Automatically Populated from Google OAuth

### User Model (core.User)
✅ **Automatically filled during Google sign-in:**
- `email` - User's Google email address
- `first_name` - Given name from Google profile
- `last_name` - Family name from Google profile
- `role` - Defaults to 'student' (can be changed by admin)

### Profile Models (StudentProfile / StaffProfile)
✅ **Automatically filled during profile creation:**
- **Student/Staff ID** - Generated from email username
  - Example: `john.doe@example.com` → `JOHN_DOE`
  - Fallback: `TEMP_{user_id}` if email format is unusual
- **Profile Picture** - Downloaded from Google profile photo
  - Saved to: `media/profiles/students/` or `media/profiles/staff/`
  - Filename: `google_profile_{user_id}.jpg`

❌ **NOT available from Google (requires manual completion):**
- Date of Birth
- Phone Number
- Emergency Contact Name
- Emergency Contact Phone
- Blood Type
- Allergies
- Medical Conditions
- Department (staff only)
- Specialization (staff only)
- License Number (staff only)

## How It Works

### Signal Flow
1. **`pre_social_login` signal** - Captures Google data BEFORE user creation
   - Extracts: email, given_name, family_name
   - Populates User model fields
   
2. **`social_account_added` signal** - Creates profile AFTER user is saved
   - Generates student/staff ID from email
   - Downloads and saves profile picture
   - Creates profile with all available data

3. **`post_save` signal (fallback)** - Ensures profile exists
   - Creates profile if social signals didn't fire
   - Useful for manual user creation in admin

### User Journey
```
Google Sign-In
    ↓
Redirect to Google OAuth
    ↓
User grants permissions (email, profile)
    ↓
Google returns user data
    ↓
pre_social_login: Populate User fields
    ↓
User created & saved
    ↓
social_account_added: Create profile with Google data
    ↓
Download profile picture from Google
    ↓
Save profile with generated ID & picture
    ↓
Redirect to dashboard (complete profile if needed)
```

## Implementation Details

### Files Modified

1. **`backend/settings.py`**
   - Added logging configuration for debugging
   - Configured Google OAuth scopes (email, profile)

2. **`core/adapters.py`** - `GoogleOnlyAdapter`
   - `populate_user()`: Extracts first_name, last_name, email from Google
   - `save_user()`: Ensures role is set (defaults to 'student')

3. **`management/models.py`** - Profile Models
   - Made all fields nullable/optional: `null=True, blank=True, default=''`
   - StudentProfile: date_of_birth, phone, emergency contacts, blood_type
   - StaffProfile: date_of_birth, phone, emergency contacts, blood_type, department

4. **`management/signals.py`** - Signal Handlers
   - `populate_user_from_google`: Captures Google data via `pre_social_login`
   - `create_profile_from_google`: Creates profile via `social_account_added`
   - `download_google_profile_picture`: Downloads & saves profile photo
   - `create_user_profile`: Fallback profile creation
   - `save_user_profile`: Auto-save profiles on user update

### Google OAuth Data Structure
```python
google_data = {
    'email': 'user@example.com',
    'given_name': 'John',
    'family_name': 'Doe',
    'picture': 'https://lh3.googleusercontent.com/...',
    'locale': 'en',
    'verified_email': True,
    'id': '1234567890'  # Google user ID
}
```

### ID Generation Logic
```python
email = "john.doe@example.com"
username = "john.doe"
generated_id = "JOHN_DOE"  # Uppercase, dots replaced with underscores
```

### Profile Picture Download
- **URL**: Google CDN (lh3.googleusercontent.com)
- **Format**: JPG (Google's default)
- **Timeout**: 10 seconds
- **Error Handling**: Fails gracefully, logs error, continues signup
- **Storage**: Django ImageField (media/profiles/students/ or staff/)

## Logging

All Google OAuth operations are logged for debugging:
```
INFO: Google OAuth data captured for user@example.com: Name: John Doe
INFO: Creating profile for user 5 (user@example.com) with role: student
INFO: Created StudentProfile with ID: JOHN_DOE
INFO: Downloading profile picture for user 5 from https://...
INFO: Successfully downloaded profile picture: google_profile_5.jpg
INFO: Saved profile picture for student user@example.com
```

## Testing the Integration

### Manual Test Steps
1. Open http://127.0.0.1:8000/accounts/google/login/
2. Sign in with a Google account
3. Check console logs for profile creation messages
4. Verify in Django admin:
   - User has first_name, last_name, email filled
   - Profile exists with generated ID
   - Profile picture is saved (if download succeeded)

### Expected Database State After Google Login
**core_user table:**
```
id=1, email=john@example.com, first_name=John, last_name=Doe, role=student
```

**management_studentprofile table:**
```
id=1, user_id=1, student_id=JOHN, profile_image=profiles/students/google_profile_1.jpg,
date_of_birth=NULL, phone='', emergency_contact='', ...
```

## Security & Privacy

### Data Handling
- ✅ Profile pictures downloaded over HTTPS
- ✅ 10-second timeout prevents hanging requests
- ✅ Errors logged but don't block signup
- ✅ Only requests minimal scopes (email, profile)
- ✅ No sensitive data stored beyond what Google provides

### Google Scopes Requested
```python
'SCOPE': ['profile', 'email']
```
- **profile**: Name, profile picture
- **email**: Email address

**Not requested:** phone, birthday, address, contacts

## Troubleshooting

### Profile not created after Google login
- Check console logs for errors
- Verify signals are registered (check `management/apps.py`)
- Ensure user has a role set

### Profile picture not downloading
- Check network connectivity to Google CDN
- Verify `requests` library is installed
- Check logs for download errors
- Picture URL may be temporary/expired

### Duplicate profile error
- Check if profile already exists
- Signals use `get_or_create` to prevent duplicates
- Clear database and retry if needed

## Future Enhancements

1. ✨ Allow users to refresh profile picture from Google
2. ✨ Add profile completion progress indicator
3. ✨ Send email reminder to complete profile after 7 days
4. ✨ Extract more data if Google adds additional scopes
5. ✨ Support other OAuth providers (Microsoft, GitHub)
6. ✨ Add profile picture cropping/resizing
