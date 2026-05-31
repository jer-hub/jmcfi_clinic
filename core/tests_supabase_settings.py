"""Settings tests for Supabase-ready database and storage configuration."""

from django.conf import settings
from django.test import SimpleTestCase, override_settings


class SupabaseSettingsTests(SimpleTestCase):
    def test_test_runner_uses_sqlite_by_default(self):
        """manage.py test forces SQLite unless TEST_DATABASE_URL is set."""
        self.assertEqual(
            settings.DATABASES["default"]["ENGINE"],
            "django.db.backends.sqlite3",
        )

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
        STORAGES={
            "default": {"BACKEND": "core.storage.SupabasePrivateStorage"},
            "staticfiles": {
                "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
            },
        },
    )
    def test_supabase_storage_backend_when_enabled(self):
        self.assertEqual(
            settings.STORAGES["default"]["BACKEND"],
            "core.storage.SupabasePrivateStorage",
        )

    def test_supabase_env_defaults_present(self):
        self.assertEqual(settings.SUPABASE_STORAGE_BUCKET, "clinic-private")
        self.assertIn("OPTIONS", settings.STORAGES["default"])
