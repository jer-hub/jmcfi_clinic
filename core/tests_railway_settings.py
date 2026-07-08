"""Settings and health endpoint tests for Railway production deployment."""

import os
from importlib import reload

from django.test import Client, SimpleTestCase, TestCase, override_settings


class RailwayHealthEndpointTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_health_liveness_returns_ok(self):
        response = self.client.get('/health/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'ok'})

    def test_health_ready_returns_ok_with_sqlite(self):
        response = self.client.get('/health/ready/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'ok')
        self.assertEqual(response.json()['database'], 'connected')


class RailwaySettingsTests(SimpleTestCase):
    def test_railway_public_domain_extends_allowed_hosts_and_csrf(self):
        os.environ['RAILWAY_PUBLIC_DOMAIN'] = 'jmcfi-clinic.up.railway.app'
        try:
            import backend.settings as settings_module

            reload(settings_module)
            self.assertIn('jmcfi-clinic.up.railway.app', settings_module.ALLOWED_HOSTS)
            self.assertIn(
                'https://jmcfi-clinic.up.railway.app',
                settings_module.CSRF_TRUSTED_ORIGINS,
            )
        finally:
            os.environ.pop('RAILWAY_PUBLIC_DOMAIN', None)
            import backend.settings as settings_module

            reload(settings_module)

    @override_settings(DEBUG=False)
    def test_proxy_ssl_header_when_not_debug(self):
        old_debug = os.environ.get('DEBUG')
        os.environ['DEBUG'] = 'False'
        try:
            import backend.settings as settings_module

            reload(settings_module)
            self.assertEqual(
                settings_module.SECURE_PROXY_SSL_HEADER,
                ('HTTP_X_FORWARDED_PROTO', 'https'),
            )
        finally:
            if old_debug is None:
                os.environ.pop('DEBUG', None)
            else:
                os.environ['DEBUG'] = old_debug
            import backend.settings as settings_module

            reload(settings_module)

    def test_whitenoise_middleware_installed(self):
        import backend.settings as settings_module

        self.assertIn(
            'whitenoise.middleware.WhiteNoiseMiddleware',
            settings_module.MIDDLEWARE,
        )

    def test_staticfiles_use_whitenoise_storage(self):
        import backend.settings as settings_module

        self.assertEqual(
            settings_module.STORAGES['staticfiles']['BACKEND'],
            'whitenoise.storage.CompressedManifestStaticFilesStorage',
        )
