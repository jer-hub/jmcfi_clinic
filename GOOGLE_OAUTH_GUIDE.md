# Google OAuth Account Chooser - Implementation Guide

## Overview

The JMCFI Clinic system is now configured to **require Google authentication** for all users. When logging in or after being logged out, users will be prompted to choose which Google account they want to use via Google's account chooser interface.

---

## Key Features

### ✅ What Was Implemented

1. **Google Account Chooser**: Users always see the Google account selection screen
2. **No Password Login**: Password-based authentication is disabled
3. **Google OAuth Required**: All authentication must go through Google
4. **Account Selection**: Users can choose which Google account to sign in with
5. **Improved Login UI**: Modern, user-friendly login interface

---

## How It Works

### User Login Flow

```
User clicks "Sign in" 
    ↓
Redirected to Google OAuth
    ↓
Google shows "Choose an account" screen
    ↓
User selects desired Google account
    ↓
Google authenticates and returns to app
    ↓
User is logged into JMCFI Clinic
```

### Account Chooser Behavior

**When users click "Continue with Google":**
- ✅ Google always shows the account chooser screen
- ✅ Users see all Google accounts they're logged into
- ✅ Users can select which account to use
- ✅ Users can add a different account if needed
- ✅ Previous account selection is NOT remembered

**Key Setting:**
```python
'AUTH_PARAMS': {
    'access_type': 'online',
    'prompt': 'select_account',  # ← Forces account chooser
}
```

---

## Configuration Details

### 1. Google OAuth Settings (`backend/settings.py`)

```python
SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'APP': {
            'client_id': 'YOUR_CLIENT_ID',
            'secret': 'YOUR_SECRET',
        },
        'SCOPE': [
            'profile',
            'email',
        ],
        'AUTH_PARAMS': {
            'access_type': 'online',
            'prompt': 'select_account',  # Forces account chooser
        },
    }
}
```

**What This Does:**
- `prompt: 'select_account'` - Forces Google to show the account chooser every time
- Users must actively choose which account to use
- No automatic login with previously used account
- Enhanced security by requiring conscious account selection

### 2. Django-allauth Configuration

```python
# Authentication settings
ACCOUNT_AUTHENTICATION_METHOD = 'email'  # Use email for authentication
ACCOUNT_EMAIL_REQUIRED = True  # Email is mandatory
ACCOUNT_USERNAME_REQUIRED = False  # No username needed
ACCOUNT_USER_MODEL_USERNAME_FIELD = None  # No username field

# Social account settings
SOCIALACCOUNT_AUTO_SIGNUP = True  # Automatic signup via Google
SOCIALACCOUNT_LOGIN_ON_GET = True  # No intermediate confirmation page
ACCOUNT_LOGOUT_ON_GET = True  # Easy logout
SOCIALACCOUNT_QUERY_EMAIL = True  # Request email from Google

# Custom adapters
ACCOUNT_ADAPTER = 'core.adapters.NoPasswordAdapter'  # Disable passwords
SOCIALACCOUNT_ADAPTER = 'core.adapters.GoogleOnlyAdapter'  # Google-only

# Email verification
ACCOUNT_EMAIL_VERIFICATION = 'none'  # No email verification needed
```

### 3. Custom Adapters (`core/adapters.py`)

**NoPasswordAdapter:**
- Disables password-based authentication
- Blocks manual signup (only Google signup allowed)
- Redirects to dashboard after login

**GoogleOnlyAdapter:**
- Handles Google social account authentication
- Populates user data from Google (name, email)
- Allows signup via Google OAuth
- Extracts first name, last name, and email from Google

---

## User Experience

### Login Page Features

**Visual Design:**
- 🎨 Modern gradient background (primary-50 to blue-50)
- 📦 Centered white card with shadow
- 🔵 Large, prominent Google sign-in button
- ℹ️ Blue info box explaining account chooser
- 📱 Fully responsive for mobile devices

**User Flow:**
1. User sees login page with single "Continue with Google" button
2. Clicks button → Redirected to Google
3. Google shows "Choose an account" screen with:
   - List of all Google accounts user is logged into
   - Option to "Use another account"
   - Profile pictures and email addresses
4. User selects desired account
5. Google authenticates and redirects back
6. User lands on dashboard

### Account Chooser Screen (Google's)

**What Users See:**
```
┌─────────────────────────────────────┐
│  Choose an account                  │
│  to continue to JMCFI Clinic        │
├─────────────────────────────────────┤
│  👤 John Doe                        │
│     john.doe@institution.edu        │
├─────────────────────────────────────┤
│  👤 Jane Smith                      │
│     jane.smith@gmail.com            │
├─────────────────────────────────────┤
│  ➕ Use another account             │
└─────────────────────────────────────┘
```

---

## Security Benefits

### Why Account Chooser is Important

1. **Prevents Account Confusion**: Users clearly see which account they're using
2. **Reduces Mistakes**: No automatic login with wrong account
3. **Shared Device Security**: Users on shared computers must choose account
4. **Multiple Account Support**: Easy to switch between institutional and personal accounts
5. **Explicit Consent**: Users actively choose which identity to use

### Additional Security Features

✅ **No Password Storage**: Passwords are handled by Google, not your app
✅ **OAuth Security**: Industry-standard authentication protocol
✅ **Email Verification**: Automatically verified by Google
✅ **Session Management**: Controlled by session timeout middleware
✅ **HTTPONLY Cookies**: Session cookies protected from JavaScript

---

## Testing Instructions

### Test 1: Account Chooser Appears

**Steps:**
1. Log out of JMCFI Clinic
2. Clear browser cache/cookies (optional but recommended)
3. Click "Continue with Google" on login page
4. **Expected**: Google shows "Choose an account" screen
5. Select an account
6. **Expected**: Logged into JMCFI Clinic

### Test 2: Multiple Accounts

**Setup:**
1. Have multiple Google accounts logged into browser
2. Log out of JMCFI Clinic

**Steps:**
1. Click "Continue with Google"
2. **Expected**: See list of all Google accounts
3. Select Account A → Login successful
4. Log out
5. Click "Continue with Google" again
6. **Expected**: See account chooser again (not auto-login with Account A)
7. Select Account B → Login successful with different account

### Test 3: Add New Account

**Steps:**
1. Click "Continue with Google"
2. On account chooser, click "Use another account"
3. **Expected**: Google shows login form
4. Enter credentials for new account
5. **Expected**: Login successful with new account

### Test 4: Forced Logout Behavior

**Steps:**
1. Log in successfully
2. Wait for session timeout OR manually log out
3. Try to access protected page
4. **Expected**: Redirected to login page
5. Click "Continue with Google"
6. **Expected**: Account chooser appears (must choose account again)

---

## Troubleshooting

### Problem: Account chooser doesn't appear

**Possible Causes:**
1. `prompt: 'select_account'` not configured
2. Browser cache remembering previous selection
3. Google OAuth settings not saved

**Solutions:**
1. Verify `AUTH_PARAMS` in settings includes `'prompt': 'select_account'`
2. Clear browser cache and cookies
3. Restart Django server
4. Test in incognito/private browsing mode

### Problem: Users see password login form

**Possible Causes:**
1. Using default allauth templates
2. Custom adapters not configured
3. Wrong URL being accessed

**Solutions:**
1. Ensure custom `login.html` template is in `templates/account/`
2. Verify `ACCOUNT_ADAPTER` setting points to `NoPasswordAdapter`
3. Check users are accessing correct login URL

### Problem: Auto-login without account chooser

**Possible Causes:**
1. Google remembering last account choice
2. `prompt` parameter not being sent
3. Browser remembering OAuth consent

**Solutions:**
1. Clear Google OAuth consents: https://myaccount.google.com/permissions
2. Test in incognito mode
3. Verify `AUTH_PARAMS` configuration
4. Check Google Cloud Console OAuth settings

### Problem: "Error 400: redirect_uri_mismatch"

**Possible Causes:**
1. Redirect URI not configured in Google Cloud Console
2. Development/production URL mismatch

**Solutions:**
1. Add redirect URI to Google Cloud Console:
   - Go to Google Cloud Console
   - Select your project
   - Go to "APIs & Services" → "Credentials"
   - Edit OAuth 2.0 Client ID
   - Add authorized redirect URIs:
     - `http://localhost:8000/accounts/google/login/callback/`
     - `https://yourdomain.com/accounts/google/login/callback/`
2. Ensure URLs match exactly (including trailing slash)

---

## Google Cloud Console Setup

### Required OAuth Configuration

**1. Authorized JavaScript Origins:**
```
http://localhost:8000
https://yourdomain.com
```

**2. Authorized Redirect URIs:**
```
http://localhost:8000/accounts/google/login/callback/
https://yourdomain.com/accounts/google/login/callback/
```

**3. OAuth Consent Screen:**
- Application name: "JMCFI Clinic"
- User support email: your email
- Scopes: email, profile (openid is automatic)
- Test users: Add test accounts if in testing mode

---

## Customization Options

### Change Account Chooser Behavior

**Current setting (Always show chooser):**
```python
'prompt': 'select_account'
```

**Alternative settings:**
```python
'prompt': 'consent'           # Always ask for consent
'prompt': 'none'              # No prompt (silent auth)
'prompt': 'login'             # Force re-authentication
'prompt': 'select_account consent'  # Both chooser and consent
```

**Recommendation:** Keep `'select_account'` for best user experience

### Additional OAuth Parameters

You can add more parameters to `AUTH_PARAMS`:

```python
'AUTH_PARAMS': {
    'access_type': 'online',
    'prompt': 'select_account',
    'hd': 'institution.edu',        # Restrict to specific domain
    'login_hint': 'user@domain.com', # Pre-fill email
    'include_granted_scopes': 'true', # Incremental auth
}
```

**Domain Restriction Example:**
```python
'hd': 'jmcfi.edu'  # Only allow accounts from @jmcfi.edu
```

---

## User Guide Content

### For End Users

**How to Sign In:**

1. **Go to login page**
   - You'll see a single "Continue with Google" button

2. **Click the Google button**
   - You'll be redirected to Google

3. **Choose your account**
   - Google will show you all your logged-in accounts
   - Select the account you want to use
   - **Important:** Use your institutional email (@jmcfi.edu or similar)

4. **Access granted**
   - You'll be redirected back and logged in
   - You'll land on your dashboard

**Tips:**
- ✅ Always use your institutional Google account
- ✅ Check which account you're selecting
- ✅ You'll need to choose your account each time you log in
- ⚠️ Don't use personal Google accounts unless instructed
- ⚠️ Remember to log out when using shared computers

**Troubleshooting for Users:**
- **Can't see my account?** Click "Use another account" to add it
- **Wrong account?** Log out and sign in again, choose correct account
- **Access denied?** Contact administrator - you may need to be added to the system

---

## Technical Comparison

### Before vs. After

| Feature | Before | After |
|---------|--------|-------|
| **Authentication** | Multiple methods possible | Google OAuth only |
| **Account Selection** | May auto-login | Always shows chooser |
| **Password Login** | Possibly enabled | Disabled |
| **User Flow** | May be confusing | Clear, single path |
| **Security** | Variable | Enhanced |
| **Account Switching** | Manual logout needed | Easy account selection |

---

## Advanced Configuration

### Environment-Based Settings

For different behavior in dev/staging/production:

**In `settings.py`:**
```python
from decouple import config

GOOGLE_OAUTH_PROMPT = config('GOOGLE_OAUTH_PROMPT', default='select_account')

SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'AUTH_PARAMS': {
            'access_type': 'online',
            'prompt': GOOGLE_OAUTH_PROMPT,
        },
    }
}
```

**In `.env`:**
```
# Development - always show chooser
GOOGLE_OAUTH_PROMPT=select_account

# Production - always show chooser (recommended)
GOOGLE_OAUTH_PROMPT=select_account
```

### Logging OAuth Events

Add logging to track authentication events:

```python
# In core/adapters.py
import logging

logger = logging.getLogger(__name__)

class GoogleOnlyAdapter(DefaultSocialAccountAdapter):
    def pre_social_login(self, request, sociallogin):
        logger.info(f"Google login attempt: {sociallogin.account.extra_data.get('email')}")
    
    def authentication_error(self, request, provider_id, error=None, exception=None, extra_context=None):
        logger.error(f"Google auth error for {provider_id}: {error}")
        super().authentication_error(request, provider_id, error, exception, extra_context)
```

---

## Maintenance

### Regular Checks

**Monthly:**
- [ ] Verify Google OAuth credentials are valid
- [ ] Check OAuth consent screen is approved
- [ ] Review authentication logs for issues
- [ ] Test login flow still works

**Quarterly:**
- [ ] Audit authorized users
- [ ] Review security settings
- [ ] Update documentation if needed
- [ ] Check for django-allauth updates

**Annually:**
- [ ] Rotate OAuth client secret
- [ ] Full security audit
- [ ] Review and update authorized domains
- [ ] Test disaster recovery procedures

---

## Rollback Procedure

### If Issues Arise

**Step 1: Remove account chooser prompt**
```python
# In settings.py
'AUTH_PARAMS': {
    'access_type': 'online',
    # Remove or comment out:
    # 'prompt': 'select_account',
}
```

**Step 2: Re-enable password login (if needed)**
```python
# In settings.py
# Comment out or remove:
# ACCOUNT_ADAPTER = 'core.adapters.NoPasswordAdapter'
```

**Step 3: Revert login template**
```bash
git checkout templates/account/login.html
```

**Step 4: Restart server**
```bash
python manage.py runserver
```

---

## Related Documentation

- [Django-allauth Documentation](https://django-allauth.readthedocs.io/)
- [Google OAuth 2.0 Documentation](https://developers.google.com/identity/protocols/oauth2)
- [Google Account Chooser](https://developers.google.com/identity/protocols/oauth2/openid-connect#prompt)

---

## Support

### For Users
- Contact IT Support or System Administrator
- Email: support@jmcfi.edu (example)
- Include screenshot of error if applicable

### For Developers
- Review this guide
- Check django-allauth documentation
- Review Google OAuth logs in Cloud Console
- Test in development environment first

---

**Last Updated**: October 21, 2025  
**Status**: ✅ Active and Deployed  
**Version**: 1.0  
**Configuration**: Google OAuth with Account Chooser Enabled
