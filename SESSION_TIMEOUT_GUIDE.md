# Session Timeout Configuration - Guide

## Overview

The JMCFI Clinic system now includes role-based session timeout management to enhance security and user experience. Different user roles have different session timeout periods based on their usage patterns and security requirements.

---

## Session Timeout Periods

### By User Role

| User Role | Session Timeout | Duration | Rationale |
|-----------|----------------|----------|-----------|
| **Admin** | 12 hours | 43,200 seconds | Admins need extended access for management tasks but with tighter security |
| **Staff** | 24 hours | 86,400 seconds | Medical staff need longer sessions for continuous patient care throughout shifts |
| **Student** | 24 hours | 86,400 seconds | Students need extended access for scheduling and checking records |

### Previous Default
- **Old timeout**: 2 weeks (Django default: 1,209,600 seconds)
- **New timeout**: Role-based (12-24 hours)

---

## How It Works

### Session Extension on Activity

The system is configured with **`SESSION_SAVE_EVERY_REQUEST = True`**, which means:

✅ **Active users stay logged in**: Every page request extends the session timeout
✅ **Automatic renewal**: Users don't need to re-login if they're actively using the system
✅ **Idle timeout**: If a user is inactive for the full timeout period, they're logged out

### Example Scenarios

#### Scenario 1: Active Staff Member
- Staff logs in at 8:00 AM
- Uses system continuously throughout the day
- **Result**: Stays logged in because each action extends the 24-hour timeout
- Session effectively never expires during active use

#### Scenario 2: Inactive Student
- Student logs in at 9:00 AM
- Closes browser but doesn't log out
- Doesn't access the system again
- **Result**: After 24 hours (next day at 9:00 AM), session expires
- Must log in again to access the system

#### Scenario 3: Admin User
- Admin logs in at 7:00 AM
- Works until 5:00 PM (10 hours)
- **Result**: Still logged in because of continuous activity
- If they leave for more than 12 hours without activity, must re-login

---

## Security Features

### Cookie Security Settings

```python
SESSION_COOKIE_HTTPONLY = True      # Prevents JavaScript access to cookies
SESSION_COOKIE_SECURE = False       # Set to True in production with HTTPS
SESSION_COOKIE_SAMESITE = 'Lax'     # CSRF protection
SESSION_EXPIRE_AT_BROWSER_CLOSE = False  # Session persists across browser sessions
```

### What This Means:

✅ **Protected from XSS attacks**: `HTTPONLY` prevents malicious JavaScript from stealing session cookies
✅ **CSRF protection**: `SAMESITE` setting helps prevent cross-site request forgery
✅ **Persistent sessions**: Users don't lose their session when closing the browser (within timeout period)
⚠️ **Production consideration**: Enable `SESSION_COOKIE_SECURE = True` when using HTTPS in production

---

## Implementation Details

### Files Modified

#### 1. `backend/settings.py`

Added session configuration:

```python
# Session Configuration
SESSION_COOKIE_AGE = 86400  # 24 hours default
SESSION_SAVE_EVERY_REQUEST = True  # Extend on activity
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = False  # Change to True in production
SESSION_COOKIE_SAMESITE = 'Lax'
```

Added middleware to MIDDLEWARE list:
```python
"core.middleware.SessionTimeoutMiddleware",  # After AuthenticationMiddleware
```

#### 2. `core/middleware.py`

Created new `SessionTimeoutMiddleware` class:

```python
class SessionTimeoutMiddleware:
    """
    Middleware to set role-specific session timeouts
    Admin: 12 hours (43200 seconds)
    Staff: 24 hours (86400 seconds)
    Student: 24 hours (86400 seconds)
    """
    def __init__(self, get_response):
        self.get_response = get_response
        self.role_timeouts = {
            'admin': 43200,    # 12 hours
            'staff': 86400,    # 24 hours
            'student': 86400,  # 24 hours
        }

    def __call__(self, request):
        if request.user.is_authenticated:
            user_role = getattr(request.user, 'role', None)
            if user_role in self.role_timeouts:
                timeout = self.role_timeouts[user_role]
                request.session.set_expiry(timeout)
        
        response = self.get_response(request)
        return response
```

---

## User Experience

### What Users See

#### When Session is Active
- ✅ Users can navigate freely
- ✅ No interruptions during active use
- ✅ Seamless experience

#### When Session Expires
- 🔒 User is redirected to login page
- 💬 May see message: "Your session has expired. Please log in again."
- 🔄 After login, users return to their dashboard

### Best Practices for Users

**For Staff and Students:**
1. ✅ Don't worry about timeouts during active use
2. ✅ System remembers your session for 24 hours
3. ⚠️ Log out manually when using shared computers
4. ⚠️ Don't share login credentials

**For Admins:**
1. ✅ 12-hour timeout balances security and convenience
2. ⚠️ More sensitive operations may require re-authentication
3. ✅ Log out when leaving admin workstation
4. ⚠️ Use secure passwords and enable 2FA if available

---

## Testing Instructions

### Test Session Timeout Manually

#### Test 1: Verify Role-Based Timeouts

**Setup:**
1. Log in as a student user
2. Open browser developer tools (F12)
3. Go to Application/Storage → Cookies
4. Find `sessionid` cookie
5. Note the expiry time

**Expected:**
- Session should be set to expire 24 hours from login time
- Each page request should extend this by 24 hours

#### Test 2: Verify Session Extension

**Setup:**
1. Log in as staff
2. Wait 1 hour
3. Click any navigation link
4. Check session expiry in cookies

**Expected:**
- Session expiry should be extended by 24 hours from the click time
- User should remain logged in

#### Test 3: Verify Idle Timeout

**Setup:**
1. Log in as admin
2. Don't interact with the system for 12+ hours
3. Try to access a page

**Expected:**
- User should be redirected to login page
- Session should be expired

### Automated Testing

Add this test to `core/tests.py`:

```python
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from datetime import timedelta
from django.utils import timezone

User = get_user_model()

class SessionTimeoutTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.staff_user = User.objects.create_user(
            email='staff@test.com',
            password='testpass123',
            role='staff',
            first_name='Test',
            last_name='Staff'
        )
        self.student_user = User.objects.create_user(
            email='student@test.com',
            password='testpass123',
            role='student',
            first_name='Test',
            last_name='Student'
        )
        
    def test_staff_session_timeout_24_hours(self):
        """Test that staff session is set to 24 hours"""
        self.client.login(email='staff@test.com', password='testpass123')
        session = self.client.session
        
        # Check session expiry is set
        self.assertIsNotNone(session.get_expiry_age())
        
        # Should be approximately 24 hours (86400 seconds)
        expiry = session.get_expiry_age()
        self.assertGreater(expiry, 86000)  # At least 23.8 hours
        self.assertLess(expiry, 87000)     # Less than 24.2 hours
        
    def test_student_session_timeout_24_hours(self):
        """Test that student session is set to 24 hours"""
        self.client.login(email='student@test.com', password='testpass123')
        session = self.client.session
        
        expiry = session.get_expiry_age()
        self.assertGreater(expiry, 86000)
        self.assertLess(expiry, 87000)
```

---

## Configuration Changes

### Adjusting Timeout Periods

To change session timeout periods, edit `core/middleware.py`:

```python
self.role_timeouts = {
    'admin': 43200,    # Change these values (in seconds)
    'staff': 86400,    
    'student': 86400,  
}
```

**Common timeout values:**
- 1 hour: `3600`
- 6 hours: `21600`
- 12 hours: `43200`
- 24 hours: `86400`
- 7 days: `604800`

### Per-Environment Configuration

For different timeouts in development vs. production, use environment variables:

**In `settings.py`:**
```python
from decouple import config

SESSION_TIMEOUT_STAFF = config('SESSION_TIMEOUT_STAFF', default=86400, cast=int)
SESSION_TIMEOUT_STUDENT = config('SESSION_TIMEOUT_STUDENT', default=86400, cast=int)
SESSION_TIMEOUT_ADMIN = config('SESSION_TIMEOUT_ADMIN', default=43200, cast=int)
```

**In `.env` file:**
```
SESSION_TIMEOUT_STAFF=172800  # 48 hours in production
SESSION_TIMEOUT_STUDENT=172800
SESSION_TIMEOUT_ADMIN=28800   # 8 hours in production
```

---

## Security Considerations

### Recommended Settings for Production

```python
# In production with HTTPS
SESSION_COOKIE_SECURE = True  # Only send cookie over HTTPS
SESSION_COOKIE_HTTPONLY = True  # Prevent JavaScript access
SESSION_COOKIE_SAMESITE = 'Strict'  # Stronger CSRF protection
DEBUG = False  # Never run debug mode in production
```

### Additional Security Measures

1. **Enable HTTPS**: Always use SSL/TLS in production
2. **Rotate SECRET_KEY**: Change regularly and keep secure
3. **Monitor sessions**: Log unusual login patterns
4. **Implement rate limiting**: Prevent brute force attacks
5. **Use strong passwords**: Enforce password policies
6. **Enable 2FA**: Add two-factor authentication for admins

---

## Troubleshooting

### Problem: Users are being logged out too quickly

**Possible Causes:**
1. `SESSION_SAVE_EVERY_REQUEST` is set to `False`
2. Timeout values are too low
3. Browser is blocking cookies

**Solutions:**
1. Verify `SESSION_SAVE_EVERY_REQUEST = True` in settings
2. Increase timeout values in middleware
3. Check browser cookie settings

### Problem: Sessions last too long

**Possible Causes:**
1. Timeout values are too high
2. `SESSION_SAVE_EVERY_REQUEST` extends indefinitely

**Solutions:**
1. Reduce timeout values in middleware
2. Consider implementing absolute session expiry
3. Add idle time tracking

### Problem: Session expires immediately on browser close

**Possible Causes:**
1. `SESSION_EXPIRE_AT_BROWSER_CLOSE` is set to `True`

**Solutions:**
1. Set `SESSION_EXPIRE_AT_BROWSER_CLOSE = False` in settings
2. Verify browser is allowing persistent cookies

---

## Monitoring and Analytics

### Session Metrics to Track

1. **Average session duration** by role
2. **Login frequency** per user
3. **Session expiry rate** (timeout vs. manual logout)
4. **Peak usage hours** by role

### Django Admin Session Management

View active sessions in Django Admin:
1. Navigate to `/admin/`
2. Go to "Sessions" 
3. See all active user sessions
4. Can manually delete sessions to force logout

---

## Migration and Rollback

### Applying Changes

Changes are applied immediately when the server restarts:

```bash
# No database migration needed
python manage.py check
python manage.py runserver
```

### Rolling Back

To revert to Django defaults:

**1. Remove middleware from `settings.py`:**
```python
MIDDLEWARE = [
    # ... other middleware ...
    # Remove this line:
    # "core.middleware.SessionTimeoutMiddleware",
]
```

**2. Remove session settings from `settings.py`:**
```python
# Delete or comment out:
# SESSION_COOKIE_AGE = 86400
# SESSION_SAVE_EVERY_REQUEST = True
# ... etc
```

**3. Restart server:**
```bash
python manage.py runserver
```

---

## Future Enhancements

### Potential Improvements

1. **Idle timeout warning**: Show countdown before logout
2. **Remember device**: Extended timeout for trusted devices
3. **Activity-based extension**: Smart timeout based on user activity level
4. **Session history**: Track login history per user
5. **Concurrent session limits**: Restrict to one session per user
6. **Geolocation tracking**: Detect unusual login locations
7. **Device fingerprinting**: Enhanced security for known devices

---

## Compliance and Privacy

### Data Protection

- ✅ Session data is stored securely server-side
- ✅ Cookie only contains session ID, not user data
- ✅ HTTPONLY prevents JavaScript access
- ✅ Compliant with GDPR session requirements

### User Privacy

- Session data is automatically deleted after expiry
- Users can clear their session by logging out
- No tracking beyond authentication needs

---

## References

- [Django Session Framework Documentation](https://docs.djangoproject.com/en/5.2/topics/http/sessions/)
- [Django Security Settings](https://docs.djangoproject.com/en/5.2/ref/settings/#sessions)
- [OWASP Session Management](https://owasp.org/www-community/controls/Session_Management_Cheat_Sheet)

---

**Last Updated**: October 21, 2025  
**Feature Status**: ✅ Active and Deployed  
**Version**: 1.0
