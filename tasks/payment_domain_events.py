from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
import logging
import uuid

from celery import shared_task
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from application.notifications.event_map import PAYMENT_EVENT_TO_TEMPLATE, payment_notification_context
from django_app.payments.models import Payment, PaymentDomainEventOutbox


logger = logging.getLogger(__name__)
MAX_PAYMENT_EVENT_ATTEMPTS = 5
EVENT_TO_TEMPLATE = PAYMENT_EVENT_TO_TEMPLATE
PAYMENT_DECIMALS = {
    "RWF": 0,
}


@shared_task(bind=True, name="tasks.payment_domain_events.publish_payment_domain_event_task", max_retries=0)
def publish_payment_domain_event_task(self, event_id: str) -> bool:
    return publish_payment_domain_event(event_id)


@shared_task(name="tasks.payment_domain_events.retry_due_payment_domain_events_task")
def retry_due_payment_domain_events_task(batch_size: int = 50) -> dict:
    now = timezone.now()
    ids = list(
        PaymentDomainEventOutbox.objects.filter(
            status=PaymentDomainEventOutbox.Status.PENDING,
        )
        .filter(next_attempt_at__isnull=True)
        .order_by("created_at")
        .values_list("id", flat=True)[:batch_size]
    )
    due_ids = list(
        PaymentDomainEventOutbox.objects.filter(
            status=PaymentDomainEventOutbox.Status.PENDING,
            next_attempt_at__lte=now,
        )
        .order_by("next_attempt_at", "created_at")
        .values_list("id", flat=True)[: max(0, batch_size - len(ids))]
    )
    published = 0
    failed = 0
    for event_id in [*ids, *due_ids]:
        try:
            if publish_payment_domain_event(event_id):
                published += 1
        except Exception:
            failed += 1
    return {"attempted": len(ids) + len(due_ids), "published": published, "failed": failed}


def publish_payment_domain_event(event_id: str | uuid.UUID) -> bool:
    with transaction.atomic():
        try:
            event = PaymentDomainEventOutbox.objects.select_for_update().get(id=event_id)
        except PaymentDomainEventOutbox.DoesNotExist:
            return False
        if event.status == PaymentDomainEventOutbox.Status.PUBLISHED:
            return True
        if event.status == PaymentDomainEventOutbox.Status.FAILED:
            return False
        event.status = PaymentDomainEventOutbox.Status.PROCESSING
        event.attempts += 1
        event.save(update_fields=["status", "attempts", "updated_at"])

    try:
        # Payment domain events are durably recorded for downstream consumers.
        with transaction.atomic():
            event = PaymentDomainEventOutbox.objects.select_for_update().get(id=event_id)
            event.status = PaymentDomainEventOutbox.Status.PUBLISHED
            event.published_at = timezone.now()
            event.last_error = None
            event.next_attempt_at = None
            event.save(update_fields=["status", "published_at", "last_error", "next_attempt_at", "updated_at"])
        try:
            _enqueue_email_notification(event)
        except Exception:
            logger.exception(
                "payment_notification_enqueue_failed",
                extra={"event_id": str(event.id), "event_type": event.event_type},
            )
        return True
    except Exception as exc:
        _mark_failed_or_pending(event_id, exc)
        raise


def _enqueue_email_notification(event: PaymentDomainEventOutbox) -> None:
    template = EVENT_TO_TEMPLATE.get(event.event_type)
    if not template:
        return

    notification = _notification_for_event(event, template)
    if notification is None:
        return

    from tasks.notifications import send_email_task

    send_email_task.delay(**notification)


def _notification_for_event(event: PaymentDomainEventOutbox, template: str) -> dict | None:
    payment = (
        Payment.objects.select_related("user")
        .filter(id=(event.payload or {}).get("payment_id") or event.aggregate_id)
        .only("id", "reference", "amount_minor", "currency", "status", "user__email")
        .first()
    )
    if payment is None or not payment.user.email:
        return None

    context = payment_notification_context(
        payment_reference=payment.reference,
        amount=_format_amount(payment.amount_minor, payment.currency),
        currency=payment.currency,
        status=payment.status,
        cta_url=_payment_url(payment.reference),
    )
    return {
        "to": payment.user.email,
        "template": template,
        "context": context,
    }


def _format_amount(amount_minor: int, currency: str) -> str:
    decimals = PAYMENT_DECIMALS.get(currency, 2)
    divisor = Decimal(10) ** decimals
    return str(Decimal(amount_minor) / divisor)


def _frontend_url() -> str:
    return (getattr(settings, "FRONTEND_URL", "") or "").strip().rstrip("/")


def _payment_url(reference: str) -> str:
    return f"{_frontend_url()}/payments/{reference}"


def _mark_failed_or_pending(event_id: str | uuid.UUID, exc: Exception) -> None:
    with transaction.atomic():
        event = PaymentDomainEventOutbox.objects.select_for_update().get(id=event_id)
        event.last_error = type(exc).__name__
        if event.attempts >= MAX_PAYMENT_EVENT_ATTEMPTS:
            event.status = PaymentDomainEventOutbox.Status.FAILED
            event.next_attempt_at = None
        else:
            event.status = PaymentDomainEventOutbox.Status.PENDING
            delay = min(2 ** event.attempts, 300)
            event.next_attempt_at = timezone.now() + timedelta(seconds=delay)
        event.save(update_fields=["status", "last_error", "next_attempt_at", "updated_at"])
