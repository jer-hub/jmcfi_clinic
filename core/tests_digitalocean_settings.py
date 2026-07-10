import importlib
import os
import uuid

from django.test import SimpleTestCase, TestCase


class DigitalOceanSettingsTests(SimpleTestCase):
    def _reload_settings(self):
        module = importlib.import_module("backend.settings")
        return importlib.reload(module)

    def test_secure_proxy_header_enabled_when_debug_false(self):
        previous_debug = os.environ.get("DEBUG")
        os.environ["DEBUG"] = "False"
        try:
            settings_mod = self._reload_settings()
            self.assertEqual(
                settings_mod.SECURE_PROXY_SSL_HEADER,
                ("HTTP_X_FORWARDED_PROTO", "https"),
            )
        finally:
            if previous_debug is None:
                del os.environ["DEBUG"]
            else:
                os.environ["DEBUG"] = previous_debug

    def test_whitenoise_manifest_storage_is_configured(self):
        settings_mod = self._reload_settings()
        self.assertEqual(
            settings_mod.STORAGES["staticfiles"]["BACKEND"],
            "whitenoise.storage.CompressedManifestStaticFilesStorage",
        )

    def test_app_domain_is_appended_to_hosts_and_csrf(self):
        unique_host = f"{uuid.uuid4().hex}.ondigitalocean.app"
        previous = os.environ.get("APP_DOMAIN")
        os.environ["APP_DOMAIN"] = unique_host
        try:
            settings_mod = self._reload_settings()
        finally:
            if previous is None:
                del os.environ["APP_DOMAIN"]
            else:
                os.environ["APP_DOMAIN"] = previous

        self.assertIn(unique_host, settings_mod.ALLOWED_HOSTS)
        self.assertIn(f"https://{unique_host}", settings_mod.CSRF_TRUSTED_ORIGINS)


class HealthEndpointTests(TestCase):
    def test_liveness_endpoint(self):
        response = self.client.get("/health/")
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {"status": "ok"})

    def test_readiness_endpoint(self):
        response = self.client.get("/health/ready/")
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(
            response.content,
            {"status": "ok", "database": "connected"},
        )
