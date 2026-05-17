"""Notification delivery for document requests (deferred until commit)."""

from __future__ import annotations

import logging

from django.db import transaction

from core.notification_delivery import deliver_bulk_notifications, notify_user
from document_request.models import DocumentRequest

from .selectors import get_assigned_doctors_for_student

logger = logging.getLogger(__name__)


def notify_assigned_clinicians_new_request(doc_request: DocumentRequest, actor) -> None:
    recipients = list(get_assigned_doctors_for_student(doc_request.student))
    if not recipients:
        logger.info(
            'No assigned doctor for document request %s (student %s); skipping notification.',
            doc_request.pk,
            doc_request.student_id,
        )
        return

    doc_label = dict(DocumentRequest.DOCUMENT_TYPES).get(doc_request.document_type, 'certificate')
    actor_name = actor.get_full_name() or actor.email
    message = (
        f'{actor_name} has requested a {doc_label} and a certificate has been auto-created for review.'
    )
    title = 'New Certificate Request'

    def _deliver():
        deliver_bulk_notifications(
            recipients,
            title,
            message,
            notification_type='certificate',
            transaction_type='certificate_requested',
            related_id=doc_request.id,
        )

    transaction.on_commit(_deliver)


def notify_student_ready(doc_request: DocumentRequest) -> None:
    title = 'Record Request Completed'
    message = f'Your {doc_request.get_document_type_display()} request is now completed.'

    def _deliver():
        notify_user(
            doc_request.student,
            title,
            message,
            notification_type='certificate',
            transaction_type='certificate_ready',
            related_id=doc_request.id,
        )

    transaction.on_commit(_deliver)


def notify_student_rejected(doc_request: DocumentRequest, reason: str) -> None:
    title = 'Certificate Request Rejected'
    message = (
        f'Your {doc_request.get_document_type_display()} request has been rejected. '
        f'Reason: {reason}'
    )

    def _deliver():
        notify_user(
            doc_request.student,
            title,
            message,
            notification_type='certificate',
            transaction_type='certificate_rejected',
            related_id=doc_request.id,
        )

    transaction.on_commit(_deliver)
