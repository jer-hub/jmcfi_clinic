import sys
from pathlib import Path

import dj_database_url
from decouple import config, Csv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config(
    "SECRET_KEY", default="d^6mjh@m%#+j#5n07@8e9tcvmh_%-)z)j1k_z%xqrt0%4p99a^"
)

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = config("DEBUG", default=True, cast=bool)

# Ensure ALLOWED_HOSTS is a list. Support comma-separated env via decouple's Csv cast.
ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="localhost,127.0.0.1", cast=Csv())

SECURE_SSL_REDIRECT = config("SECURE_SSL_REDIRECT", default=not DEBUG, cast=bool)
SESSION_COOKIE_SECURE = config("SESSION_COOKIE_SECURE", default=not DEBUG, cast=bool)
CSRF_COOKIE_SECURE = config("CSRF_COOKIE_SECURE", default=not DEBUG, cast=bool)
SECURE_HSTS_SECONDS = config("SECURE_HSTS_SECONDS", default=31536000 if not DEBUG else 0, cast=int)
SECURE_HSTS_INCLUDE_SUBDOMAINS = config("SECURE_HSTS_INCLUDE_SUBDOMAINS", default=not DEBUG, cast=bool)
SECURE_HSTS_PRELOAD = config("SECURE_HSTS_PRELOAD", default=not DEBUG, cast=bool)
ADMIN_LOGIN_REQUIRE_HTTPS_REDIRECT = config(
    "ADMIN_LOGIN_REQUIRE_HTTPS_REDIRECT",
    default=not DEBUG,
    cast=bool,
)

# Silence django-allauth deprecation warnings (we use stable format for OAuth-only setup)

# Application definition
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "channels",
    'django.contrib.sites',  # Required for django-allauth
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    'django_extensions',
    # Core apps
    "core",
    # Service apps
    "appointments",
    "medical_records",
    "dental_records",
    "document_request",
    "feedback",
    "health_tips",
    "health_forms_services",
    "analytics",
    "pharmacy",
    "messaging",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
        "core.middleware.UserActivityMiddleware",  # Track last user activity
        "core.middleware.SessionTimeoutMiddleware",  # Role-based session timeout
    "core.middleware.MaintenanceModeMiddleware",
    "core.middleware.RoleFeatureAccessMiddleware",
    "core.middleware.RoleMiddleware",
    "core.middleware.ProfileCompleteMiddleware",  # Require complete profile for access
    "core.access_middleware.HtmxAccessResponseMiddleware",
    "core.htmx_utils.HTMXMiddleware",
]

# Provider specific settings
GOOGLE_CLIENT_ID = config('GOOGLE_CLIENT_ID', default='')
GOOGLE_CLIENT_SECRET = config('GOOGLE_CLIENT_SECRET', default='')
GOOGLE_ALLOWED_DOMAINS = config('GOOGLE_ALLOWED_DOMAINS', default='', cast=Csv())

SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'APP': {
            'client_id': GOOGLE_CLIENT_ID,
            'secret': GOOGLE_CLIENT_SECRET,
        },
        'SCOPE': [
            'profile',
            'email',
        ],
        'AUTH_PARAMS': {
            'access_type': 'online',
            'prompt': 'select_account',  # Force Google account chooser
        },
        'OAUTH_PKCE_ENABLED': True,  # Enable PKCE for enhanced security
        'FETCH_USER_INFO': True,  # Fetch user info from Google
        'EMAIL_AUTHENTICATION': True,  # Use email for authentication
    }
}

# Django-allauth configuration (new format)
ACCOUNT_LOGIN_METHODS = {'email'}  # Use email for authentication
ACCOUNT_SIGNUP_FIELDS = ['email*', 'password1*', 'password2*']  # Required signup fields
ACCOUNT_USER_MODEL_USERNAME_FIELD = None  # No username field
ACCOUNT_AUTHENTICATED_LOGIN_REDIRECTS = True  # Logged-in users cannot access login page
SOCIALACCOUNT_AUTO_SIGNUP = True  # Skip the signup form if possible
SOCIALACCOUNT_LOGIN_ON_GET = True  # Skip the intermediate page on login
ACCOUNT_LOGOUT_ON_GET = False  # Require POST logout to avoid CSRF/logout-forcing
SOCIALACCOUNT_QUERY_EMAIL = True  # Request email from provider
ACCOUNT_ADAPTER = 'core.adapters.NoPasswordAdapter'  # Disable password login
SOCIALACCOUNT_ADAPTER = 'core.adapters.GoogleOnlyAdapter'  # Google-only social login

# Disable email verification for smoother Google login
ACCOUNT_EMAIL_VERIFICATION = 'none'  # Don't require email verification

ROOT_URLCONF = "backend.urls"
ASGI_APPLICATION = "backend.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [
            BASE_DIR / "templates",
        ],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.notification_context",
                "core.context_processors.profile_context",
                "core.context_processors.clinic_settings_context",
                "core.context_processors.role_features_context",
                "core.context_processors.user_preferences_context",
                "core.nav_context.nav_bar_context",
            ],
        },
    },
]

WSGI_APPLICATION = "backend.wsgi.application"

REDIS_URL = config("REDIS_URL", default="")

if REDIS_URL:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {
                "hosts": [REDIS_URL],
            },
        }
    }
else:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer",
        }
    }


# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases

_SQLITE_DATABASE = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

DATABASE_URL = config("DATABASE_URL", default="")
TEST_DATABASE_URL = config("TEST_DATABASE_URL", default="")

_running_tests = "test" in sys.argv
_use_test_db_url = _running_tests and bool(TEST_DATABASE_URL)

if _running_tests and not TEST_DATABASE_URL:
    DATABASES = _SQLITE_DATABASE
elif _use_test_db_url:
    DATABASES = {
        "default": dj_database_url.parse(
            TEST_DATABASE_URL,
            conn_max_age=0,
        )
    }
elif DATABASE_URL:
    _local_supabase = DATABASE_URL.startswith(
        "postgresql://postgres:postgres@127.0.0.1"
    ) or DATABASE_URL.startswith("postgresql://postgres:postgres@localhost")
    DATABASES = {
        "default": dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=600,
            conn_health_checks=True,
            ssl_require=not _local_supabase,
        )
    }
else:
    DATABASES = _SQLITE_DATABASE


# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

AUTHENTICATION_BACKENDS = (
    'django.contrib.auth.backends.ModelBackend',  # Default backend
    'allauth.account.auth_backends.AuthenticationBackend',  # Required
)


AUTH_USER_MODEL = "core.User"

SITE_ID = 1
LOGIN_URL = 'account_login'  # Redirect to login page if not authenticated
LOGIN_REDIRECT_URL = 'core:dashboard'
LOGOUT_REDIRECT_URL = 'account_login'  # Redirect to login page after logout
CSRF_FAILURE_VIEW = 'core.views.csrf_failure'

# Session Configuration
# Session timeout settings (in seconds)
# Default Django timeout is 1209600 seconds (2 weeks)
SESSION_COOKIE_AGE = 86400  # 24 hours (1 day) for staff and students
SESSION_SAVE_EVERY_REQUEST = True  # Extend session on every request (keep users logged in while active)
SESSION_EXPIRE_AT_BROWSER_CLOSE = False  # Don't expire when browser closes
SESSION_COOKIE_HTTPONLY = True  # Prevent JavaScript access to session cookies (security)
SESSION_COOKIE_SAMESITE = 'Lax'  # CSRF protection

# Role-specific session timeouts (will be set in custom middleware)
# Admin: 12 hours (43200 seconds)
# Staff: 24 hours (86400 seconds) 
# Patient: 24 hours (86400 seconds)

# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "Asia/Manila"

USE_I18N = True

USE_TZ = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "staticfiles"]
STATIC_ROOT = BASE_DIR / "static"

# Media files (uploaded files)
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Supabase Storage (S3-compatible) — server-side only; never expose keys to the browser
USE_SUPABASE_STORAGE = config("USE_SUPABASE_STORAGE", default=False, cast=bool)
SUPABASE_URL = config("SUPABASE_URL", default="").rstrip("/")
SUPABASE_STORAGE_BUCKET = config("SUPABASE_STORAGE_BUCKET", default="clinic-private")
SUPABASE_PUBLIC_STORAGE_BUCKET = config(
    "SUPABASE_PUBLIC_STORAGE_BUCKET", default="clinic-public"
)
SUPABASE_S3_ACCESS_KEY_ID = config("SUPABASE_S3_ACCESS_KEY_ID", default="")
SUPABASE_S3_SECRET_ACCESS_KEY = config("SUPABASE_S3_SECRET_ACCESS_KEY", default="")

from core.supabase_config import resolve_supabase_s3_region

SUPABASE_S3_REGION = resolve_supabase_s3_region(
    config("SUPABASE_S3_REGION", default=""),
    SUPABASE_URL,
    config("DATABASE_URL", default=""),
)

if SUPABASE_URL:
    SUPABASE_S3_ENDPOINT_URL = f"{SUPABASE_URL}/storage/v1/s3"
else:
    SUPABASE_S3_ENDPOINT_URL = config("SUPABASE_S3_ENDPOINT_URL", default="")

_FILESYSTEM_STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
        "OPTIONS": {
            "location": MEDIA_ROOT,
            "base_url": MEDIA_URL,
        },
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

if USE_SUPABASE_STORAGE and SUPABASE_S3_ENDPOINT_URL and SUPABASE_S3_ACCESS_KEY_ID:
    STORAGES = {
        "default": {
            "BACKEND": "core.storage.SupabasePrivateStorage",
        },
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }
else:
    STORAGES = _FILESYSTEM_STORAGES
    USE_SUPABASE_STORAGE = False

# PDF generation engine path (wkhtmltopdf)
WKHTMLTOPDF_CMD = config("WKHTMLTOPDF_CMD", default="")

# Email (console backend in dev; override via EMAIL_BACKEND in production)
EMAIL_BACKEND = config(
    "EMAIL_BACKEND",
    default="django.core.mail.backends.console.EmailBackend",
)
DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", default="clinic@jmcfi.edu.ph")
SERVER_EMAIL = config("SERVER_EMAIL", default=DEFAULT_FROM_EMAIL)

# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Logging configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'management.signals': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'allauth': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'security.auth': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# Appointment Scheduling Configuration
# Buffer interval between consecutive appointments (in minutes)
# Prevents double-booking; minimum 15, maximum 120 recommended
APPOINTMENT_INTERVAL_MINUTES = 30
