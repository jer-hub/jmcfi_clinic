"""Shared helpers for pharmacy tests."""

import uuid

from django.test import override_settings

STRIPPED_MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',
    'core.middleware.SessionTimeoutMiddleware',
    'core.middleware.RoleMiddleware',
]


def make_user(role='staff', email=None, **kwargs):
    from django.contrib.auth import get_user_model

    User = get_user_model()
    email = email or f'{role}-{uuid.uuid4().hex[:8]}@pharm.test'
    return User.objects.create_user(email=email, password='test1234', role=role, **kwargs)


pharmacy_test_settings = override_settings(MIDDLEWARE=STRIPPED_MIDDLEWARE)
