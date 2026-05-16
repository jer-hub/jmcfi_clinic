"""Audit event logging for document requests."""

from __future__ import annotations

from document_request.models import DocumentRequestEvent


def log_event(*, request, actor, event_type: str, payload: dict | None = None) -> None:
    DocumentRequestEvent.objects.create(
        request=request,
        actor=actor,
        event_type=event_type,
        payload=payload or {},
    )
