"""Settings tests for Supabase-ready database and storage configuration."""

from django.conf import settings
from django.test import SimpleTestCase, override_settings

from core.supabase_config import resolve_supabase_s3_region

_FILESYSTEM_STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
        "OPTIONS": {
            "location": settings.MEDIA_ROOT,
            "base_url": settings.MEDIA_URL,
        },
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

_SUPABASE_STORAGES = {
    "default": {"BACKEND": "core.storage.SupabasePrivateStorage"},
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}


class SupabaseS3RegionTests(SimpleTestCase):
    def test_local_cli_uses_local_region(self):
        self.assertEqual(
            resolve_supabase_s3_region("", "http://127.0.0.1:54321", ""),
            "local",
        )

    def test_hosted_infers_region_from_pooler_url(self):
        self.assertEqual(
            resolve_supabase_s3_region(
                "local",
                "https://abc.supabase.co",
                "postgresql://postgres.abc:pw@aws-1-ap-southeast-1.pooler.supabase.com:5432/postgres",
            ),
            "ap-southeast-1",
        )

    def test_hosted_explicit_region_wins(self):
        self.assertEqual(
            resolve_supabase_s3_region(
                "eu-west-1",
                "https://abc.supabase.co",
                "postgresql://postgres.abc:pw@aws-1-ap-southeast-1.pooler.supabase.com:5432/postgres",
            ),
            "eu-west-1",
        )


class SupabaseSettingsTests(SimpleTestCase):
    def test_test_runner_uses_sqlite_by_default(self):
        """manage.py test forces SQLite unless TEST_DATABASE_URL is set."""
        self.assertEqual(
            settings.DATABASES["default"]["ENGINE"],
            "django.db.backends.sqlite3",
        )

    @override_settings(USE_SUPABASE_STORAGE=False, STORAGES=_FILESYSTEM_STORAGES)
    def test_default_storage_is_filesystem_without_supabase(self):
        self.assertFalse(settings.USE_SUPABASE_STORAGE)
        self.assertEqual(
            settings.STORAGES["default"]["BACKEND"],
            "django.core.files.storage.FileSystemStorage",
        )

    @override_settings(
        USE_SUPABASE_STORAGE=True,
        SUPABASE_URL="http://127.0.0.1:54321",
        SUPABASE_S3_ENDPOINT_URL="http://127.0.0.1:54321/storage/v1/s3",
        SUPABASE_S3_ACCESS_KEY_ID="test-key",
        SUPABASE_S3_SECRET_ACCESS_KEY="test-secret",
        STORAGES=_SUPABASE_STORAGES,
    )
    def test_supabase_storage_backend_when_enabled(self):
        self.assertEqual(
            settings.STORAGES["default"]["BACKEND"],
            "core.storage.SupabasePrivateStorage",
        )

    @override_settings(USE_SUPABASE_STORAGE=False, STORAGES=_FILESYSTEM_STORAGES)
    def test_supabase_env_defaults_present(self):
        self.assertEqual(settings.SUPABASE_STORAGE_BUCKET, "clinic-private")
        self.assertIn("OPTIONS", settings.STORAGES["default"])
