"""Supabase Storage (S3-compatible) backends for django-storages."""

from django.conf import settings
from storages.backends.s3 import S3Storage


def _supabase_s3_options(bucket_name: str) -> dict:
    """Shared OPTIONS for Supabase S3-compatible storage."""
    return {
        "bucket_name": bucket_name,
        "access_key": settings.SUPABASE_S3_ACCESS_KEY_ID,
        "secret_key": settings.SUPABASE_S3_SECRET_ACCESS_KEY,
        "endpoint_url": settings.SUPABASE_S3_ENDPOINT_URL,
        "region_name": settings.SUPABASE_S3_REGION,
        "addressing_style": "path",
        "signature_version": "s3v4",
        "file_overwrite": False,
        "default_acl": "private",
        "querystring_auth": True,
        "querystring_expire": 3600,
    }


class SupabasePrivateStorage(S3Storage):
    """Private bucket for PHI: profiles, signatures, certificates."""

    def __init__(self, **settings_dict):
        options = _supabase_s3_options(settings.SUPABASE_STORAGE_BUCKET)
        options.update(settings_dict)
        super().__init__(**options)


class SupabasePublicStorage(S3Storage):
    """Optional public bucket for health-tip markdown images."""

    def __init__(self, **settings_dict):
        bucket = getattr(
            settings,
            "SUPABASE_PUBLIC_STORAGE_BUCKET",
            settings.SUPABASE_STORAGE_BUCKET,
        )
        options = _supabase_s3_options(bucket)
        options["default_acl"] = "public-read"
        options["querystring_auth"] = False
        options.update(settings_dict)
        super().__init__(**options)
