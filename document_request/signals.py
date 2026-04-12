from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import MedicalCertificate


@receiver(post_save, sender=MedicalCertificate)
def sync_certificate_status_to_document_requests(sender, instance, **kwargs):
    """
    When a MedicalCertificate's status changes, propagate the new status
    to every linked DocumentRequest so there is only ONE status to manage.
    Also notify the student when the certificate is completed.
    """
    from core.models import Notification  # late import to avoid circular

    linked_requests = instance.document_requests.select_related('student').all()
    if not linked_requests.exists():
        return

    linked_requests.update(status=instance.status)

    # Notify the student when the certificate becomes completed (= ready)
    if instance.status == 'completed':
        students_notified = set()
        for doc_request in linked_requests:
            if doc_request.student_id not in students_notified:
                Notification.objects.create(
                    user=doc_request.student,
                    title='Certificate Ready',
                    message='Your medical certificate is ready for viewing.',
                    notification_type='certificate',
                    transaction_type='certificate_ready',
                    related_id=doc_request.id,
                )
                students_notified.add(doc_request.student_id)
