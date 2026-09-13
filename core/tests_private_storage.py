from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.test import TestCase, override_settings
from django.urls import reverse
from django.conf import settings

from core.doctor_access import MODULE_FILES
from core.models import PatientProfile
from core.tests import _complete_staff_like_profile, _complete_student_profile
from document_request.models import DocumentRequest, MedicalCertificate
from files.models import DriveItem

User = get_user_model()


@override_settings(
    MIDDLEWARE=[
        middleware
        for middleware in settings.MIDDLEWARE
        if middleware != 'core.middleware.ProfileCompleteMiddleware'
    ]
)
class PrivateStorageAclTests(TestCase):
    def setUp(self):
        self.patient_a = User.objects.create_user(
            email='patient-a-storage@test.com',
            password='pass',
            role='patient',
            first_name='Pat',
            last_name='A',
        )
        _complete_student_profile(self.patient_a, 'PAT-STOR-A')
        self.patient_b = User.objects.create_user(
            email='patient-b-storage@test.com',
            password='pass',
            role='patient',
            first_name='Pat',
            last_name='B',
        )
        _complete_student_profile(self.patient_b, 'PAT-STOR-B')

        self.staff = User.objects.create_user(
            email='staff-storage@test.com',
            password='pass',
            role='staff',
            first_name='Staff',
            last_name='Stor',
        )
        _complete_staff_like_profile(self.staff, 'STAFF-STOR-01')
        profile = self.staff.staff_profile
        profile.allowed_clinical_modules = [MODULE_FILES]
        profile.save(update_fields=['allowed_clinical_modules'])

        self.admin = User.objects.create_user(
            email='admin-storage@test.com',
            password='pass',
            role='admin',
            first_name='Admin',
            last_name='Stor',
        )
        _complete_staff_like_profile(self.admin, 'ADM-STOR-01')

    def _url(self, path):
        return reverse('core:private_storage', kwargs={'path': path})

    def _store(self, path, content=b'fake-image'):
        default_storage.save(path, ContentFile(content))
        self.addCleanup(lambda: default_storage.delete(path) if default_storage.exists(path) else None)
        return path

    def test_traversal_rejected(self):
        self.client.force_login(self.staff)
        response = self.client.get(self._url('profiles/../secrets.txt'))
        self.assertEqual(response.status_code, 404)

    def test_unknown_prefix_denied(self):
        path = self._store('secrets/hidden.txt')
        self.client.force_login(self.staff)
        response = self.client.get(self._url(path))
        self.assertEqual(response.status_code, 404)

    def test_patient_cannot_fetch_other_patient_profile(self):
        path = self._store('profiles/patients/patient-b.jpg')
        PatientProfile.objects.filter(user=self.patient_b).update(profile_image=path)

        self.client.force_login(self.patient_a)
        response = self.client.get(self._url(path))
        self.assertEqual(response.status_code, 404)

    def test_patient_can_fetch_own_profile(self):
        path = self._store('profiles/patients/patient-a.jpg')
        PatientProfile.objects.filter(user=self.patient_a).update(profile_image=path)

        self.client.force_login(self.patient_a)
        response = self.client.get(self._url(path))
        self.assertEqual(response.status_code, 200)

    def test_staff_can_fetch_patient_profile(self):
        path = self._store('profiles/patients/patient-b2.jpg')
        PatientProfile.objects.filter(user=self.patient_b).update(profile_image=path)

        self.client.force_login(self.staff)
        response = self.client.get(self._url(path))
        self.assertEqual(response.status_code, 200)

    def test_clinic_logo_any_authenticated(self):
        path = self._store('clinic/logo.png')
        self.client.force_login(self.patient_a)
        response = self.client.get(self._url(path))
        self.assertEqual(response.status_code, 200)

    def test_patient_cannot_fetch_other_certificate_pdf(self):
        path = self._store('certificates/issued/cert-b.pdf', b'%PDF-1.4')
        doc = DocumentRequest.objects.create(
            patient=self.patient_b,
            document_type='medical_certificate',
            status=DocumentRequest.Status.COMPLETED,
        )
        MedicalCertificate.objects.create(
            user=self.patient_b,
            document_request=doc,
            patient_name='Pat B',
            status=MedicalCertificate.Status.ISSUED,
            issued_pdf=path,
        )

        self.client.force_login(self.patient_a)
        response = self.client.get(self._url(path))
        self.assertEqual(response.status_code, 404)

    def test_owner_can_fetch_issued_certificate_pdf(self):
        path = self._store('certificates/issued/cert-a.pdf', b'%PDF-1.4')
        doc = DocumentRequest.objects.create(
            patient=self.patient_a,
            document_type='medical_certificate',
            status=DocumentRequest.Status.COMPLETED,
        )
        MedicalCertificate.objects.create(
            user=self.patient_a,
            document_request=doc,
            patient_name='Pat A',
            status=MedicalCertificate.Status.ISSUED,
            issued_pdf=path,
        )

        self.client.force_login(self.patient_a)
        response = self.client.get(self._url(path))
        self.assertEqual(response.status_code, 200)

    def test_patient_cannot_fetch_drive_file(self):
        path = self._store('drive/1/file.txt', b'hello')
        DriveItem.objects.create(
            kind=DriveItem.Kind.FILE,
            name='file.txt',
            owner=self.staff,
            file=path,
            size_bytes=5,
            content_type='text/plain',
        )
        self.client.force_login(self.patient_a)
        response = self.client.get(self._url(path))
        self.assertEqual(response.status_code, 404)

    def test_staff_with_module_can_fetch_drive_file(self):
        path = self._store('drive/1/ok.txt', b'hello')
        DriveItem.objects.create(
            kind=DriveItem.Kind.FILE,
            name='ok.txt',
            owner=self.staff,
            file=path,
            size_bytes=5,
            content_type='text/plain',
        )
        self.client.force_login(self.staff)
        response = self.client.get(self._url(path))
        self.assertEqual(response.status_code, 200)

    def test_admin_cannot_fetch_drive_via_proxy(self):
        """Drive UI is staff/doctor only; mirror that on the proxy."""
        path = self._store('drive/1/admin-denied.txt', b'hello')
        DriveItem.objects.create(
            kind=DriveItem.Kind.FILE,
            name='admin-denied.txt',
            owner=self.staff,
            file=path,
            size_bytes=5,
            content_type='text/plain',
        )
        self.client.force_login(self.admin)
        response = self.client.get(self._url(path))
        self.assertEqual(response.status_code, 404)

    def test_unlinked_profile_path_denied(self):
        path = self._store('profiles/patients/orphan.jpg')
        self.client.force_login(self.staff)
        response = self.client.get(self._url(path))
        self.assertEqual(response.status_code, 404)
