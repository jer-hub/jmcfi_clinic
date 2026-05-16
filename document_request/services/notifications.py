"""Notification delivery for document requests (deferred until commit)."""

from __future__ import annotations

import logging

from django.db import transaction

from core.models import Notification
from document_request.models import DocumentRequest

from .selectors import get_assigned_doctors_for_student

logger = logging.getLogger(__name__)


def _bulk_create_on_commit(notifications: list[Notification]) -> None:
    if not notifications:
        return

    def _create():
        Notification.objects.bulk_create(notifications)

    transaction.on_commit(_create)


def _create_on_commit(notification: Notification) -> None:
    def _create():
        notification.save()

    transaction.on_commit(_create)


def notify_assigned_clinicians_new_request(doc_request: DocumentRequest, actor) -> None:
    recipients = get_assigned_doctors_for_student(doc_request.student)
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
    _bulk_create_on_commit(
        [
            Notification(
                user=clinician,
                title='New Certificate Request',
                message=message,
                notification_type='certificate',
                transaction_type='certificate_requested',
                related_id=doc_request.id,
            )
            for clinician in recipients
        ]
    )


def notify_student_ready(doc_request: DocumentRequest) -> None:
    _create_on_commit(
        Notification(
            user=doc_request.student,
            title='Record Request Completed',
            message=f'Your {doc_request.get_document_type_display()} request is now completed.',
            notification_type='certificate',
            transaction_type='certificate_ready',
            related_id=doc_request.id,
        )
    )


def notify_student_rejected(doc_request: DocumentRequest, reason: str) -> None:
    _create_on_commit(
        Notification(
            user=doc_request.student,
            title='Certificate Request Rejected',
            message=(
                f'Your {doc_request.get_document_type_display()} request has been rejected. '
                f'Reason: {reason}'
            ),
            notification_type='certificate',
            transaction_type='certificate_rejected',
            related_id=doc_request.id,
        )
    )
