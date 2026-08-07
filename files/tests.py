from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.conf import settings

from core.doctor_access import MODULE_FILES
from core.tests import _complete_staff_like_profile

from .models import DriveItem
from . import services

User = get_user_model()


@override_settings(
    MIDDLEWARE=[
        middleware
        for middleware in settings.MIDDLEWARE
        if middleware != 'core.middleware.ProfileCompleteMiddleware'
    ]
)
class ClinicFilesTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            email='staff-files@test.com',
            password='pass',
            role='staff',
            first_name='Staff',
            last_name='Files',
        )
        _complete_staff_like_profile(self.staff, 'STAFF-FILES-01')
        profile = self.staff.staff_profile
        profile.allowed_clinical_modules = [MODULE_FILES]
        profile.save(update_fields=['allowed_clinical_modules'])

        self.doctor_denied = User.objects.create_user(
            email='doctor-files-denied@test.com',
            password='pass',
            role='doctor',
            first_name='Doc',
            last_name='Denied',
            is_staff=True,
        )
        _complete_staff_like_profile(self.doctor_denied, 'DOC-FILES-DENIED')
        denied = self.doctor_denied.staff_profile
        denied.allowed_clinical_modules = []
        denied.save(update_fields=['allowed_clinical_modules'])

        self.patient = User.objects.create_user(
            email='patient-files@test.com',
            password='pass',
            role='patient',
            first_name='Pat',
            last_name='Ient',
        )

    def _login_staff(self):
        self.client.force_login(self.staff)

    def test_patient_cannot_browse(self):
        self.client.force_login(self.patient)
        response = self.client.get(reverse('files:browse'))
        self.assertIn(response.status_code, (302, 403))
        if response.status_code == 302:
            self.assertIn('restricted', response.url)

    def test_doctor_without_module_denied(self):
        self.client.force_login(self.doctor_denied)
        response = self.client.get(reverse('files:browse'), follow=True)
        self.assertIn(response.status_code, (200, 403))
        if response.status_code == 200:
            self.assertContains(response, 'Not enabled for your account')

    def test_staff_browse_and_create_folder(self):
        self._login_staff()
        response = self.client.get(reverse('files:browse'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'My Drive')

        response = self.client.post(
            reverse('files:folder_create'),
            {'name': 'Reports'},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        folder = DriveItem.objects.get(name='Reports', kind=DriveItem.Kind.FOLDER)
        self.assertIsNone(folder.parent_id)
        self.assertEqual(folder.owner_id, self.staff.id)

    def test_upload_download_and_duplicate_name(self):
        self._login_staff()
        folder = services.create_folder(owner=self.staff, parent=None, name='Docs')
        upload = SimpleUploadedFile('note.txt', b'hello clinic', content_type='text/plain')
        response = self.client.post(
            reverse('files:upload'),
            {'parent_id': str(folder.pk), 'files': upload},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        item = DriveItem.objects.get(name='note.txt', kind=DriveItem.Kind.FILE)
        self.assertEqual(item.parent_id, folder.pk)

        download = self.client.get(reverse('files:download', args=[item.pk]))
        self.assertEqual(download.status_code, 200)
        self.assertEqual(b''.join(download.streaming_content), b'hello clinic')

        dup = SimpleUploadedFile('note.txt', b'again', content_type='text/plain')
        response = self.client.post(
            reverse('files:upload'),
            {'parent_id': str(folder.pk), 'files': dup},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            DriveItem.objects.filter(parent=folder, name='note.txt', trashed_at__isnull=True).count(),
            1,
        )

    def test_upload_json_returns_progress_payload(self):
        self._login_staff()
        folder = services.create_folder(owner=self.staff, parent=None, name='AjaxDocs')
        upload = SimpleUploadedFile('ajax.txt', b'payload', content_type='text/plain')
        response = self.client.post(
            reverse('files:upload'),
            {'parent_id': str(folder.pk), 'files': upload},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            HTTP_ACCEPT='application/json',
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['ok'])
        self.assertEqual(data['created'], 1)
        self.assertEqual(data['folder_id'], folder.pk)
        self.assertIn('browse_url', data)
        self.assertTrue(DriveItem.objects.filter(name='ajax.txt', parent=folder).exists())

    def test_download_rejects_folder(self):
        self._login_staff()
        folder = services.create_folder(owner=self.staff, parent=None, name='NoDownload')
        response = self.client.get(reverse('files:download', args=[folder.pk]))
        self.assertEqual(response.status_code, 404)

    def test_patient_cannot_download(self):
        self._login_staff()
        upload = SimpleUploadedFile('secret.txt', b'secret', content_type='text/plain')
        item = services.create_file(owner=self.staff, parent=None, uploaded_file=upload)
        self.client.force_login(self.patient)
        response = self.client.get(reverse('files:download', args=[item.pk]))
        self.assertIn(response.status_code, (302, 403))
        if response.status_code == 302:
            self.assertIn('restricted', response.url)

    def test_rename_move_cycle_blocked(self):
        self._login_staff()
        root = services.create_folder(owner=self.staff, parent=None, name='Root')
        child = services.create_folder(owner=self.staff, parent=root, name='Child')
        grandchild = services.create_folder(owner=self.staff, parent=child, name='Grand')

        response = self.client.post(
            reverse('files:rename', args=[grandchild.pk]),
            {'name': 'Grand Renamed'},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        grandchild.refresh_from_db()
        self.assertEqual(grandchild.name, 'Grand Renamed')

        # Moving root into grandchild must fail
        response = self.client.post(
            reverse('files:move', args=[root.pk]),
            {'parent_id': str(grandchild.pk)},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        root.refresh_from_db()
        self.assertIsNone(root.parent_id)

    def test_trash_restore_purge(self):
        self._login_staff()
        folder = services.create_folder(owner=self.staff, parent=None, name='Temp')
        upload = SimpleUploadedFile('temp.txt', b'x', content_type='text/plain')
        file_item = services.create_file(owner=self.staff, parent=folder, uploaded_file=upload)

        self.client.post(reverse('files:item_trash', args=[folder.pk]), follow=True)
        folder.refresh_from_db()
        file_item.refresh_from_db()
        self.assertIsNotNone(folder.trashed_at)
        self.assertIsNotNone(file_item.trashed_at)

        self.client.post(reverse('files:restore', args=[file_item.pk]), follow=True)
        file_item.refresh_from_db()
        self.assertIsNone(file_item.trashed_at)

        self.client.post(reverse('files:item_trash', args=[file_item.pk]), follow=True)
        self.client.post(reverse('files:purge', args=[file_item.pk]), follow=True)
        self.assertFalse(DriveItem.objects.filter(pk=file_item.pk).exists())

    def test_bulk_restore_purge_and_empty_trash(self):
        self._login_staff()
        a = services.create_folder(owner=self.staff, parent=None, name='BulkA')
        b = services.create_folder(owner=self.staff, parent=None, name='BulkB')
        c = services.create_folder(owner=self.staff, parent=None, name='BulkC')
        for folder in (a, b, c):
            self.client.post(reverse('files:item_trash', args=[folder.pk]), follow=True)

        response = self.client.post(
            reverse('files:trash_bulk_restore'),
            {'item_ids': [str(a.pk), str(b.pk)]},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        a.refresh_from_db()
        b.refresh_from_db()
        c.refresh_from_db()
        self.assertIsNone(a.trashed_at)
        self.assertIsNone(b.trashed_at)
        self.assertIsNotNone(c.trashed_at)

        self.client.post(reverse('files:item_trash', args=[a.pk]), follow=True)
        response = self.client.post(
            reverse('files:trash_bulk_purge'),
            {'item_ids': [str(a.pk)]},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(DriveItem.objects.filter(pk=a.pk).exists())
        self.assertTrue(DriveItem.objects.filter(pk=c.pk, trashed_at__isnull=False).exists())

        response = self.client.post(reverse('files:trash_empty'), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(DriveItem.objects.filter(trashed_at__isnull=False).exists())
        self.assertTrue(DriveItem.objects.filter(pk=b.pk, trashed_at__isnull=True).exists())

    def test_drive_bulk_trash(self):
        self._login_staff()
        a = services.create_folder(owner=self.staff, parent=None, name='DriveBulkA')
        b = services.create_folder(owner=self.staff, parent=None, name='DriveBulkB')
        response = self.client.post(
            reverse('files:bulk_trash'),
            {'item_ids': [str(a.pk), str(b.pk)]},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        a.refresh_from_db()
        b.refresh_from_db()
        self.assertIsNotNone(a.trashed_at)
        self.assertIsNotNone(b.trashed_at)

    def test_search_finds_item(self):
        self._login_staff()
        services.create_folder(owner=self.staff, parent=None, name='UniqueSearchFolder')
        response = self.client.get(reverse('files:search'), {'q': 'UniqueSearch'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'UniqueSearchFolder')

    def test_reject_exe_upload(self):
        self._login_staff()
        bad = SimpleUploadedFile('virus.exe', b'MZ', content_type='application/octet-stream')
        with self.assertRaises(Exception):
            services.create_file(owner=self.staff, parent=None, uploaded_file=bad)
