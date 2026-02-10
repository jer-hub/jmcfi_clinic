from pathlib import Path
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

# Silence django-allauth deprecation warnings (we use stable format for OAuth-only setup)

# Application definition
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
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
    "core.middleware.SessionTimeoutMiddleware",  # Role-based session timeout
    "core.middleware.RoleMiddleware",
    # "core.middleware.ProfileCompleteMiddleware",  # Disabled - users can access services without complete profile
]

# Provider specific settings
SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'APP': {
            'client_id': '936663134353-d6q81jljo4l9sgbvui75snb0cejuvntu.apps.googleusercontent.com',
            'secret': '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',
        },
        'SCOPE': [
            'profile',
            'email',
        ],
        'AUTH_PARAMS': {
            'access_type': 'online',
            'prompt': 'select_account',  # Force Google account chooser
        },
    }
}

# Django-allauth configuration (new format)
ACCOUNT_LOGIN_METHODS = {'email'}  # Use email for authentication
ACCOUNT_SIGNUP_FIELDS = ['email*', 'password1*', 'password2*']  # Required signup fields
ACCOUNT_USER_MODEL_USERNAME_FIELD = None  # No username field
SOCIALACCOUNT_AUTO_SIGNUP = True  # Skip the signup form if possible
SOCIALACCOUNT_LOGIN_ON_GET = True  # Skip the intermediate page on login
ACCOUNT_LOGOUT_ON_GET = True  # Allow logout via GET request
SOCIALACCOUNT_QUERY_EMAIL = True  # Request email from provider
ACCOUNT_ADAPTER = 'core.adapters.NoPasswordAdapter'  # Disable password login
SOCIALACCOUNT_ADAPTER = 'core.adapters.GoogleOnlyAdapter'  # Google-only social login

# Disable email verification for smoother Google login
ACCOUNT_EMAIL_VERIFICATION = 'none'  # Don't require email verification

ROOT_URLCONF = "backend.urls"

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
            ],
        },
    },
]

WSGI_APPLICATION = "backend.wsgi.application"


# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}


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

# Session Configuration
# Session timeout settings (in seconds)
# Default Django timeout is 1209600 seconds (2 weeks)
SESSION_COOKIE_AGE = 86400  # 24 hours (1 day) for staff and students
SESSION_SAVE_EVERY_REQUEST = True  # Extend session on every request (keep users logged in while active)
SESSION_EXPIRE_AT_BROWSER_CLOSE = False  # Don't expire when browser closes
SESSION_COOKIE_HTTPONLY = True  # Prevent JavaScript access to session cookies (security)
SESSION_COOKIE_SECURE = False  # Set to True in production with HTTPS
SESSION_COOKIE_SAMESITE = 'Lax'  # CSRF protection

# Role-specific session timeouts (will be set in custom middleware)
# Admin: 12 hours (43200 seconds)
# Staff: 24 hours (86400 seconds) 
# Student: 24 hours (86400 seconds) 

# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "staticfiles"]
STATIC_ROOT = BASE_DIR / "static"

# Media files (uploaded files)
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

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
    },
}
