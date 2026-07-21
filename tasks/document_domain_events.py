from __future__ import annotations

from datetime import timedelta
import logging
import uuid

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from application.notifications.event_map import DOCUMENT_EVENT_TO_TEMPLATE, export_notification_context
from django_app.documents.models import DocumentDomainEventOutbox, ExportJob


logger = logging.getLogger(__name__)
MAX_DOCUMENT_EVENT_ATTEMPTS = 5
EVENT_TO_TEMPLATE = DOCUMENT_EVENT_TO_TEMPLATE


@shared_task(bind=True, name="tasks.document_domain_events.publish_document_domain_event_task", max_retries=0)
def publish_document_domain_event_task(self, event_id: str) -> bool:
    return publish_document_domain_event(event_id)


@shared_task(name="tasks.document_domain_events.retry_due_document_domain_events_task")
def retry_due_document_domain_events_task(batch_size: int = 50) -> dict:
    now = timezone.now()
    ids = list(
        DocumentDomainEventOutbox.objects.filter(
            status=DocumentDomainEventOutbox.Status.PENDING,
        )
        .filter(next_attempt_at__isnull=True)
        .order_by("created_at")
        .values_list("id", flat=True)[:batch_size]
    )
    due_ids = list(
        DocumentDomainEventOutbox.objects.filter(
            status=DocumentDomainEventOutbox.Status.PENDING,
            next_attempt_at__lte=now,
        )
        .order_by("next_attempt_at", "created_at")
        .values_list("id", flat=True)[: max(0, batch_size - len(ids))]
    )
    published = 0
    failed = 0
    for event_id in [*ids, *due_ids]:
        try:
            if publish_document_domain_event(event_id):
                published += 1
        except Exception:
            failed += 1
    return {"attempted": len(ids) + len(due_ids), "published": published, "failed": failed}


def publish_document_domain_event(event_id: str | uuid.UUID) -> bool:
    with transaction.atomic():
        try:
            event = DocumentDomainEventOutbox.objects.select_for_update().get(id=event_id)
        except DocumentDomainEventOutbox.DoesNotExist:
            return False
        if event.status == DocumentDomainEventOutbox.Status.PUBLISHED:
            return True
        if event.status == DocumentDomainEventOutbox.Status.FAILED:
            return False
        event.status = DocumentDomainEventOutbox.Status.PROCESSING
        event.attempts += 1
        event.save(update_fields=["status", "attempts", "updated_at"])

    try:
        # Document domain events are durably recorded for downstream consumers.
        with transaction.atomic():
            event = DocumentDomainEventOutbox.objects.select_for_update().get(id=event_id)
            event.status = DocumentDomainEventOutbox.Status.PUBLISHED
            event.published_at = timezone.now()
            event.last_error = None
            event.next_attempt_at = None
            event.save(update_fields=["status", "published_at", "last_error", "next_attempt_at", "updated_at"])
        try:
            _enqueue_email_notification(event)
        except Exception:
            logger.exception(
                "document_notification_enqueue_failed",
                extra={"event_id": str(event.id), "event_type": event.event_type},
            )
        return True
    except Exception as exc:
        _mark_failed_or_pending(event_id, exc)
        raise


def _enqueue_email_notification(event: DocumentDomainEventOutbox) -> None:
    template = EVENT_TO_TEMPLATE.get(event.event_type)
    if not template:
        return

    notification = _notification_for_event(event, template)
    if notification is None:
        return

    from tasks.notifications import send_email_task

    send_email_task.delay(**notification)


def _notification_for_event(event: DocumentDomainEventOutbox, template: str) -> dict | None:
    job = (
        ExportJob.objects.select_related("event", "requested_by")
        .filter(id=(event.payload or {}).get("job_id") or event.aggregate_id)
        .only("id", "export_type", "file_url", "event__name", "requested_by__email")
        .first()
    )
    if job is None or not job.requested_by.email or not job.file_url:
        return None

    context = export_notification_context(
        event_name=job.event.name,
        export_type=job.get_export_type_display(),
        file_url=job.file_url,
        cta_url=job.file_url,
    )
    return {
        "to": job.requested_by.email,
        "template": template,
        "context": context,
    }


def _mark_failed_or_pending(event_id: str | uuid.UUID, exc: Exception) -> None:
    with transaction.atomic():
        event = DocumentDomainEventOutbox.objects.select_for_update().get(id=event_id)
        event.last_error = type(exc).__name__
        if event.attempts >= MAX_DOCUMENT_EVENT_ATTEMPTS:
            event.status = DocumentDomainEventOutbox.Status.FAILED
            event.next_attempt_at = None
        else:
            event.status = DocumentDomainEventOutbox.Status.PENDING
            delay = min(2 ** event.attempts, 300)
            event.next_attempt_at = timezone.now() + timedelta(seconds=delay)
        event.save(update_fields=["status", "last_error", "next_attempt_at", "updated_at"])
