from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from django.urls import reverse

from core.access_control import (
    AccessReason,
    access_denied_response,
    restricted_access_url,
)
from core.decorators import role_required

User = get_user_model()


@role_required('admin')
def _admin_only_view(request):
    from django.http import HttpResponse

    return HttpResponse('ok')


class AccessControlTests(TestCase):
    def setUp(self):
        self.patient = User.objects.create_user(
            email='access-patient@jmcfi.edu.ph',
            password='pass',
            role='patient',
        )

    def test_restricted_access_page_renders(self):
        response = self.client.get(reverse('core:restricted_access'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'permission')

    def test_clinical_admin_redirect_does_not_flash_toast_message(self):
        from core.tests import _complete_staff_like_profile

        admin = User.objects.create_user(
            email='access-admin-clinical@jmcfi.edu.ph',
            password='pass',
            role='admin',
        )
        _complete_staff_like_profile(admin, 'ADM-CLIN-001')
        self.client.force_login(admin)
        session = self.client.session
        session[f'profile_complete_{admin.id}_{admin.role}'] = True
        session.save()
        response = self.client.get(
            reverse('health_forms_services:forms_list'),
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Clinical area restricted')
        self.assertNotContains(
            response,
            "Admin access is not permitted for clinical application pages.",
        )

    def test_restricted_access_hides_admin_signin_for_authenticated_admin(self):
        admin = User.objects.create_user(
            email='access-admin2@jmcfi.edu.ph',
            password='pass',
            role='admin',
        )
        self.client.force_login(admin)
        response = self.client.get(reverse('core:restricted_access'))
        self.assertNotContains(response, 'Secure admin sign-in')
        self.assertContains(response, 'Signed in as administrator')

    def test_htmx_unauthenticated_dashboard_returns_401_hx_redirect(self):
        response = self.client.get('/', HTTP_HX_REQUEST='true')
        self.assertEqual(response.status_code, 401)
        self.assertIn('HX-Redirect', response)
        self.assertIn('login', response['HX-Redirect'].lower())

    def test_role_required_htmx_forbidden(self):
        from django.contrib.messages.storage.fallback import FallbackStorage

        factory = RequestFactory()
        req = factory.get('/fake/', HTTP_HX_REQUEST='true')
        req.user = self.patient
        setattr(req, 'session', self.client.session)
        req._messages = FallbackStorage(req)
        response = _admin_only_view(req)
        self.assertEqual(response.status_code, 403)
        self.assertIn('HX-Redirect', response)
        self.assertIn('restricted', response['HX-Redirect'])

    def test_access_denied_response_full_page_redirect(self):
        factory = RequestFactory()
        req = factory.get('/protected/')
        req.user = self.patient
        response = access_denied_response(
            req,
            status_code=403,
            reason=AccessReason.FORBIDDEN,
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn('restricted', response.url)

    def test_restricted_access_url_builds_query(self):
        url = restricted_access_url(
            reason=AccessReason.CSRF,
            next_url='/appointments/',
        )
        self.assertIn('reason=csrf', url)
        self.assertIn('next=%2Fappointments%2F', url)

    def test_htmx_middleware_converts_login_redirect(self):
        self.client.logout()
        response = self.client.get(
            reverse('core:notifications'),
            HTTP_HX_REQUEST='true',
        )
        self.assertEqual(response.status_code, 401)
        self.assertIn('HX-Redirect', response)
