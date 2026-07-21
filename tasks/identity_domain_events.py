from __future__ import annotations

from datetime import timedelta
import uuid

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from django_app.identity.models import IdentityDomainEventOutbox


MAX_IDENTITY_EVENT_ATTEMPTS = 5


@shared_task(bind=True, name="tasks.identity_domain_events.publish_identity_domain_event_task", max_retries=0)
def publish_identity_domain_event_task(self, event_id: str) -> bool:
    return publish_identity_domain_event(event_id)


@shared_task(name="tasks.identity_domain_events.retry_due_identity_domain_events_task")
def retry_due_identity_domain_events_task(batch_size: int = 50) -> dict:
    now = timezone.now()
    ids = list(
        IdentityDomainEventOutbox.objects.filter(
            status=IdentityDomainEventOutbox.Status.PENDING,
        )
        .filter(next_attempt_at__isnull=True)
        .order_by("created_at")
        .values_list("id", flat=True)[:batch_size]
    )
    due_ids = list(
        IdentityDomainEventOutbox.objects.filter(
            status=IdentityDomainEventOutbox.Status.PENDING,
            next_attempt_at__lte=now,
        )
        .order_by("next_attempt_at", "created_at")
        .values_list("id", flat=True)[: max(0, batch_size - len(ids))]
    )
    published = 0
    failed = 0
    for event_id in [*ids, *due_ids]:
        try:
            if publish_identity_domain_event(event_id):
                published += 1
        except Exception:
            failed += 1
    return {"attempted": len(ids) + len(due_ids), "published": published, "failed": failed}


def publish_identity_domain_event(event_id: str | uuid.UUID) -> bool:
    with transaction.atomic():
        try:
            event = IdentityDomainEventOutbox.objects.select_for_update().get(id=event_id)
        except IdentityDomainEventOutbox.DoesNotExist:
            return False
        if event.status == IdentityDomainEventOutbox.Status.PUBLISHED:
            return True
        if event.status == IdentityDomainEventOutbox.Status.FAILED:
            return False
        event.status = IdentityDomainEventOutbox.Status.PROCESSING
        event.attempts += 1
        event.save(update_fields=["status", "attempts", "updated_at"])

    try:
        # Identity domain events are durably recorded for downstream consumers. No
        # external side effect is required yet, so publishing marks the event observable.
        with transaction.atomic():
            event = IdentityDomainEventOutbox.objects.select_for_update().get(id=event_id)
            event.status = IdentityDomainEventOutbox.Status.PUBLISHED
            event.published_at = timezone.now()
            event.last_error = None
            event.next_attempt_at = None
            event.save(update_fields=["status", "published_at", "last_error", "next_attempt_at", "updated_at"])
        return True
    except Exception as exc:
        _mark_failed_or_pending(event_id, exc)
        raise


def _mark_failed_or_pending(event_id: str | uuid.UUID, exc: Exception) -> None:
    with transaction.atomic():
        event = IdentityDomainEventOutbox.objects.select_for_update().get(id=event_id)
        event.last_error = type(exc).__name__
        if event.attempts >= MAX_IDENTITY_EVENT_ATTEMPTS:
            event.status = IdentityDomainEventOutbox.Status.FAILED
            event.next_attempt_at = None
        else:
            event.status = IdentityDomainEventOutbox.Status.PENDING
            delay = min(2 ** event.attempts, 300)
            event.next_attempt_at = timezone.now() + timedelta(seconds=delay)
        event.save(update_fields=["status", "last_error", "next_attempt_at", "updated_at"])
