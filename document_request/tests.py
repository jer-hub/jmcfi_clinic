from datetime import date, time

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.test.utils import override_settings
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile

from appointments.models import Appointment, AppointmentTypeDefault
from core.models import Notification, StaffProfile, StudentProfile, User
from document_request.models import ClinicianSignature, DocumentRequest, MedicalCertificate

DoctorSignature = ClinicianSignature
from document_request.services import get_assigned_doctors_for_student


@override_settings(
    MIDDLEWARE=[
        middleware
        for middleware in settings.MIDDLEWARE
        if middleware != 'core.middleware.ProfileCompleteMiddleware'
    ]
)
class DocumentRequestFlowTests(TestCase):
    def setUp(self):
        self.student = User.objects.create_user(
            email='student@example.com',
            password='pass1234',
            role='student',
            first_name='Test',
            last_name='Student',
        )
        student_profile, _ = StudentProfile.objects.get_or_create(user=self.student)
        student_profile.student_id = 'S-1001'
        student_profile.date_of_birth = '2004-01-01'
        student_profile.phone = '09123456789'
        student_profile.emergency_contact = 'Parent'
        student_profile.emergency_phone = '09999999999'
        student_profile.blood_type = 'O+'
        student_profile.save()

        self.doctor = User.objects.create_user(
            email='doctor@example.com',
            password='pass1234',
            role='doctor',
            first_name='Doc',
            last_name='Tor',
            is_staff=True,
        )
        staff_profile, _ = StaffProfile.objects.get_or_create(user=self.doctor)
        staff_profile.staff_id = 'D-2001'
        staff_profile.department = 'Health Services'
        staff_profile.phone = '09112223333'
        staff_profile.license_number = 'LIC-001'
        staff_profile.ptr_no = 'PTR-001'
        staff_profile.save()

        self.staff = User.objects.create_user(
            email='staff@example.com',
            password='pass1234',
            role='staff',
            first_name='Clinic',
            last_name='Staff',
            is_staff=True,
        )
        StaffProfile.objects.get_or_create(user=self.staff)

        self.admin = User.objects.create_user(
            email='admin@example.com',
            password='pass1234',
            role='admin',
            first_name='Admin',
            last_name='User',
            is_staff=True,
        )

    def test_student_medical_record_request_rejected(self):
        self.client.force_login(self.student)
        response = self.client.post(
            reverse('document_request:request_document'),
            {'document_type': 'medical_record', 'purpose': 'Employment requirement'},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.request['PATH_INFO'], reverse('document_request:request_document'))
        self.assertFalse(
            DocumentRequest.objects.filter(
                student=self.student,
                document_type='medical_record',
            ).exists()
        )

    def test_student_medical_certificate_request_succeeds(self):
        self.client.force_login(self.student)
        response = self.client.post(
            reverse('document_request:request_document'),
            {'document_type': 'medical_certificate', 'purpose': 'Scholarship requirement'},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.request['PATH_INFO'], reverse('document_request:document_requests'))
        created = DocumentRequest.objects.filter(
            student=self.student,
            document_type='medical_certificate',
        ).first()
        self.assertIsNotNone(created)
        self.assertEqual(created.request_origin, 'student')
        self.assertEqual(created.created_by, self.student)

    def test_new_request_notifies_assigned_appointment_doctor(self):
        Appointment.objects.create(
            student=self.student,
            doctor=self.doctor,
            appointment_type='consultation',
            date=date.today(),
            time=time(9, 0),
            reason='Checkup',
            status='confirmed',
        )
        self.client.force_login(self.student)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(
                reverse('document_request:request_document'),
                {'document_type': 'medical_certificate', 'purpose': 'Scholarship'},
                follow=True,
            )
        self.assertEqual(
            Notification.objects.filter(
                user=self.doctor,
                transaction_type='certificate_requested',
            ).count(),
            1,
        )
        self.assertEqual(
            Notification.objects.filter(transaction_type='certificate_requested').count(),
            1,
        )

    def test_get_assigned_doctors_falls_back_to_consultation_default(self):
        type_default, _ = AppointmentTypeDefault.objects.get_or_create(
            appointment_type='consultation',
            defaults={'is_active': True},
        )
        type_default.assigned_doctors.add(self.doctor)
        assigned = get_assigned_doctors_for_student(self.student)
        self.assertEqual(len(assigned), 1)
        self.assertEqual(assigned[0].pk, self.doctor.pk)

    def test_student_request_missing_purpose_shows_error_summary(self):
        self.client.force_login(self.student)
        response = self.client.post(
            reverse('document_request:request_document'),
            {'document_type': 'medical_certificate', 'purpose': ''},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="doc-req-inline-error-purpose"')
        self.assertContains(response, 'Purpose is required.')
        self.assertNotContains(response, 'id="doc-request-errors-summary"')
        self.assertNotContains(response, 'Please fix the following')

    def test_doctor_request_missing_student_and_purpose_shows_all_errors(self):
        self.client.force_login(self.doctor)
        response = self.client.post(
            reverse('document_request:request_document'),
            {
                'source': 'doctor_on_behalf',
                'document_type': 'medical_certificate',
                'purpose': '',
                'student_id': '',
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="doc-req-inline-error-student_id"')
        self.assertContains(response, 'id="doc-req-inline-error-purpose"')
        self.assertContains(response, 'Please select a student from the search results.')
        self.assertContains(response, 'Purpose is required.')
        self.assertNotContains(response, 'id="doc-request-errors-summary"')
        self.assertFalse(DocumentRequest.objects.exists())

    def test_doctor_duplicate_pending_shows_error_on_form(self):
        self._create_pending_request()
        self.client.force_login(self.doctor)
        response = self.client.post(
            reverse('document_request:request_document'),
            {
                'source': 'doctor_on_behalf',
                'document_type': 'medical_certificate',
                'purpose': 'Another reason',
                'student_id': str(self.student.pk),
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="doc-request-warnings-summary"')
        self.assertContains(response, 'border-warning-200')
        self.assertContains(response, 'Pending request exists')
        self.assertContains(response, 'already has a pending medical certificate request')
        self.assertNotContains(response, 'id="doc-request-errors-summary"')
        self.assertEqual(
            DocumentRequest.objects.filter(
                student=self.student,
                document_type='medical_certificate',
                status=DocumentRequest.Status.PENDING_REVIEW,
            ).count(),
            1,
        )

    def test_student_medical_certificate_request_leaves_physician_name_blank(self):
        self.client.force_login(self.student)
        self.client.post(
            reverse('document_request:request_document'),
            {'document_type': 'medical_certificate', 'purpose': 'Scholarship requirement'},
            follow=True,
        )
        created = DocumentRequest.objects.get(
            student=self.student,
            document_type='medical_certificate',
        )
        self.assertEqual(created.medical_certificate.physician_name, '')

    def test_staff_can_access_document_requests_list(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse('document_request:document_requests'))
        self.assertEqual(response.status_code, 200)

    def test_list_search_matches_student_full_name(self):
        self.student.first_name = 'Jerwin'
        self.student.last_name = 'Aran'
        self.student.save(update_fields=['first_name', 'last_name'])
        doc_request = self._create_pending_request()
        other = User.objects.create_user(
            email='other@example.com',
            password='pass1234',
            role='student',
            first_name='Other',
            last_name='Person',
        )
        DocumentRequest.objects.create(
            student=other,
            created_by=other,
            document_type='medical_certificate',
            purpose='Other',
            status=DocumentRequest.Status.PENDING_REVIEW,
        )
        self.client.force_login(self.staff)
        response = self.client.get(
            reverse('document_request:document_requests'),
            {'search': 'jerwin aran'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, doc_request.purpose)
        self.assertNotContains(response, 'Other')

    def test_staff_can_access_clinician_signature_page(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse('document_request:clinician_signature'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'My Signature')

    def test_student_cannot_access_clinician_signature_page(self):
        self.client.force_login(self.student)
        response = self.client.get(reverse('document_request:clinician_signature'))
        self.assertEqual(response.status_code, 403)

    def test_complete_requires_signature_for_doctor(self):
        doc_request = self._create_pending_request()
        cert = doc_request.medical_certificate
        cert.diagnosis = 'Fit for work'
        cert.remarks_recommendations = 'Rest advised'
        cert.save()

        self.client.force_login(self.doctor)
        response = self.client.post(
            reverse('document_request:document_request_detail', args=[doc_request.pk]),
            {'action': 'review'},
        )
        self.assertEqual(response.status_code, 200)
        doc_request.refresh_from_db()
        self.assertEqual(doc_request.status, DocumentRequest.Status.PENDING_REVIEW)
        self.assertContains(response, 'Upload your signature')

    def test_complete_with_signature_succeeds(self):
        doc_request = self._create_pending_request()
        cert = doc_request.medical_certificate
        cert.diagnosis = 'Fit for work'
        cert.remarks_recommendations = 'Rest advised'
        cert.save()

        DoctorSignature.objects.create(
            doctor=self.doctor,
            signature_image=SimpleUploadedFile(
                'sig.png', b'\x89PNG\r\n\x1a\n', content_type='image/png'
            ),
            updated_by=self.doctor,
        )

        self.client.force_login(self.doctor)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                reverse('document_request:document_request_detail', args=[doc_request.pk]),
                {'action': 'review'},
                follow=True,
            )
        self.assertEqual(response.status_code, 200)
        doc_request.refresh_from_db()
        cert.refresh_from_db()
        self.assertEqual(doc_request.status, DocumentRequest.Status.COMPLETED)
        self.assertEqual(cert.status, MedicalCertificate.Status.ISSUED)
        self.assertEqual(cert.signed_by_id, self.doctor.id)
        self.assertTrue(cert.signature_snapshot.name)
        self.assertEqual(
            Notification.objects.filter(
                user=self.student,
                transaction_type='certificate_ready',
            ).count(),
            1,
        )

    def test_admin_complete_requires_signature(self):
        doc_request = self._create_pending_request()
        cert = doc_request.medical_certificate
        cert.diagnosis = 'Cleared'
        cert.remarks_recommendations = 'No restrictions'
        cert.save()

        self.client.force_login(self.admin)
        response = self.client.post(
            reverse('document_request:document_request_detail', args=[doc_request.pk]),
            {'action': 'review'},
        )
        self.assertEqual(response.status_code, 200)
        doc_request.refresh_from_db()
        self.assertEqual(doc_request.status, DocumentRequest.Status.PENDING_REVIEW)
        self.assertContains(response, 'Upload your signature')

    def _create_pending_request(self):
        cert = MedicalCertificate.objects.create(
            user=self.student,
            patient_name='Test Student',
            diagnosis='',
            remarks_recommendations='',
            status=MedicalCertificate.Status.DRAFT,
        )
        doc_request = DocumentRequest.objects.create(
            student=self.student,
            created_by=self.student,
            document_type='medical_certificate',
            purpose='Test',
            status=DocumentRequest.Status.PENDING_REVIEW,
            medical_certificate=cert,
        )
        cert.document_request = doc_request
        cert.save(update_fields=['document_request'])
        return doc_request

    def test_rejected_request_hides_certificate_actions_on_detail(self):
        doc_request = self._create_pending_request()
        self.client.force_login(self.doctor)
        self.client.post(
            reverse('document_request:document_request_detail', args=[doc_request.pk]),
            {'action': 'reject', 'rejection_reason': 'Not eligible'},
            follow=True,
        )
        doc_request.refresh_from_db()
        self.assertEqual(doc_request.status, DocumentRequest.Status.REJECTED)

        response = self.client.get(
            reverse('document_request:document_request_detail', args=[doc_request.pk]),
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'View Certificate')
        self.assertNotContains(response, 'Edit Certificate')
        self.assertNotContains(response, '>Actions<')
        self.assertContains(response, 'Rejection Reason')
        self.assertContains(response, 'Not eligible')

    def test_rejected_request_blocks_certificate_preview_and_edit(self):
        doc_request = self._create_pending_request()
        cert = doc_request.medical_certificate
        self.client.force_login(self.doctor)
        self.client.post(
            reverse('document_request:document_request_detail', args=[doc_request.pk]),
            {'action': 'reject', 'rejection_reason': 'Incomplete records'},
        )
        doc_request.refresh_from_db()
        self.assertEqual(doc_request.status, DocumentRequest.Status.REJECTED)

        detail_url = reverse('document_request:document_request_detail', args=[doc_request.pk])
        preview_url = reverse('document_request:preview_medical_certificate', args=[cert.pk])
        edit_url = reverse('document_request:edit_medical_certificate', args=[cert.pk])

        self.assertRedirects(self.client.get(preview_url), detail_url)
        self.assertRedirects(self.client.get(edit_url), detail_url)
