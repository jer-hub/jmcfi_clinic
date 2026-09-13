import importlib
import os
import uuid
from contextlib import contextmanager

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, TestCase, override_settings

_TEST_SECRET = "test-secret-key-not-for-production-use-only"


class DigitalOceanSettingsTests(SimpleTestCase):
    def _reload_settings(self):
        module = importlib.import_module("backend.settings")
        return importlib.reload(module)

    @contextmanager
    def _env(self, **updates):
        previous = {key: os.environ.get(key) for key in updates}
        try:
            for key, value in updates.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
            yield
        finally:
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    def test_secure_proxy_header_enabled_when_debug_false(self):
        with self._env(
            DEBUG="False",
            SECRET_KEY=_TEST_SECRET,
            ACCOUNT_DEFAULT_HTTP_PROTOCOL=None,
            APP_DOMAIN=None,
            CUSTOM_DOMAIN=None,
        ):
            settings_mod = self._reload_settings()
            self.assertEqual(
                settings_mod.SECURE_PROXY_SSL_HEADER,
                ("HTTP_X_FORWARDED_PROTO", "https"),
            )
            self.assertTrue(settings_mod.USE_X_FORWARDED_HOST)
            self.assertEqual(settings_mod.ACCOUNT_DEFAULT_HTTP_PROTOCOL, "https")

    def test_debug_true_with_app_domain_raises(self):
        with self._env(
            DEBUG="True",
            SECRET_KEY=_TEST_SECRET,
            ACCOUNT_DEFAULT_HTTP_PROTOCOL=None,
            APP_DOMAIN="seal-app-22qre.ondigitalocean.app",
            CUSTOM_DOMAIN=None,
        ):
            with self.assertRaises(ImproperlyConfigured):
                self._reload_settings()
        with self._env(
            DEBUG="True",
            SECRET_KEY=_TEST_SECRET,
            APP_DOMAIN=None,
            CUSTOM_DOMAIN=None,
        ):
            self._reload_settings()

    def test_debug_false_with_default_secret_raises(self):
        from backend.settings import _DEFAULT_INSECURE_SECRET

        with self._env(
            DEBUG="False",
            SECRET_KEY=_DEFAULT_INSECURE_SECRET,
            APP_DOMAIN=None,
            CUSTOM_DOMAIN=None,
        ):
            with self.assertRaises(ImproperlyConfigured):
                self._reload_settings()
        with self._env(
            DEBUG="True",
            SECRET_KEY=_TEST_SECRET,
            APP_DOMAIN=None,
            CUSTOM_DOMAIN=None,
        ):
            self._reload_settings()

    def test_app_domain_with_default_secret_raises(self):
        from backend.settings import _DEFAULT_INSECURE_SECRET

        with self._env(
            DEBUG="False",
            SECRET_KEY=_DEFAULT_INSECURE_SECRET,
            APP_DOMAIN="seal-app-22qre.ondigitalocean.app",
            CUSTOM_DOMAIN=None,
        ):
            with self.assertRaises(ImproperlyConfigured):
                self._reload_settings()
        with self._env(
            DEBUG="True",
            SECRET_KEY=_TEST_SECRET,
            APP_DOMAIN=None,
            CUSTOM_DOMAIN=None,
        ):
            self._reload_settings()

    def test_local_debug_allows_default_secret(self):
        from backend.settings import _DEFAULT_INSECURE_SECRET

        with self._env(
            DEBUG="True",
            SECRET_KEY=_DEFAULT_INSECURE_SECRET,
            APP_DOMAIN=None,
            CUSTOM_DOMAIN=None,
        ):
            settings_mod = self._reload_settings()
            self.assertTrue(settings_mod.DEBUG)
            self.assertEqual(settings_mod.SECRET_KEY, _DEFAULT_INSECURE_SECRET)

    def test_whitenoise_manifest_storage_is_configured(self):
        settings_mod = self._reload_settings()
        self.assertEqual(
            settings_mod.STORAGES["staticfiles"]["BACKEND"],
            "whitenoise.storage.CompressedManifestStaticFilesStorage",
        )

    def test_app_domain_is_appended_to_hosts_and_csrf(self):
        unique_host = f"{uuid.uuid4().hex}.ondigitalocean.app"
        with self._env(
            DEBUG="False",
            SECRET_KEY=_TEST_SECRET,
            APP_DOMAIN=unique_host,
            CUSTOM_DOMAIN=None,
        ):
            settings_mod = self._reload_settings()
            self.assertIn(unique_host, settings_mod.ALLOWED_HOSTS)
            self.assertIn(f"https://{unique_host}", settings_mod.CSRF_TRUSTED_ORIGINS)

    def test_normalize_star_wildcard_allowed_host(self):
        from backend.settings import _normalize_allowed_host

        self.assertEqual(
            _normalize_allowed_host("*.ondigitalocean.app"),
            ".ondigitalocean.app",
        )
        self.assertEqual(
            _normalize_allowed_host("app.ondigitalocean.app"),
            "app.ondigitalocean.app",
        )

    def test_star_wildcard_app_domain_not_added_to_csrf(self):
        with self._env(
            DEBUG="False",
            SECRET_KEY=_TEST_SECRET,
            APP_DOMAIN="*.ondigitalocean.app",
            CUSTOM_DOMAIN=None,
        ):
            settings_mod = self._reload_settings()
            self.assertIn(".ondigitalocean.app", settings_mod.ALLOWED_HOSTS)
            self.assertNotIn("https://*.ondigitalocean.app", settings_mod.CSRF_TRUSTED_ORIGINS)
            self.assertNotIn("https://.ondigitalocean.app", settings_mod.CSRF_TRUSTED_ORIGINS)


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

    def test_health_accepts_private_ip_host_header(self):
        """App Platform readiness probes use the pod private IP as Host."""
        response = self.client.get(
            "/health/",
            HTTP_HOST="10.244.53.17:8080",
        )
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {"status": "ok"})

    def test_health_accepts_do_mesh_ip_host_header(self):
        """App Platform also probes via 100.64/10 mesh/CGNAT Host values."""
        response = self.client.get(
            "/health/",
            HTTP_HOST="100.127.19.14:8080",
        )
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {"status": "ok"})

    @override_settings(
        ALLOWED_HOSTS=[".ondigitalocean.app", "testserver"],
        APP_DOMAIN="*.ondigitalocean.app",
        CUSTOM_DOMAIN="",
    )
    def test_health_check_skips_wildcard_fallback_host(self):
        """Wildcard APP_DOMAIN must not be written into META['HTTP_HOST']."""
        response = self.client.get(
            "/health/",
            HTTP_HOST="100.127.235.50:8080",
        )
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {"status": "ok"})

    @override_settings(
        ALLOWED_HOSTS=[".ondigitalocean.app", "testserver"],
        APP_DOMAIN=".ondigitalocean.app",
        CUSTOM_DOMAIN="",
    )
    def test_health_check_synthesizes_host_from_leading_dot(self):
        response = self.client.get(
            "/health/",
            HTTP_HOST="10.244.1.23:8080",
        )
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {"status": "ok"})

    def test_health_fallback_host_never_returns_wildcard(self):
        from core.middleware import _health_fallback_host

        with override_settings(
            APP_DOMAIN="*.ondigitalocean.app",
            CUSTOM_DOMAIN="",
            ALLOWED_HOSTS=["*.ondigitalocean.app"],
        ):
            host = _health_fallback_host()
        self.assertNotIn("*", host)
        self.assertEqual(host, "health.ondigitalocean.app")
