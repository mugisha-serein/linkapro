import json
import logging
from typing import Optional, Tuple

from celery import shared_task
from django.utils import timezone

from django_app.payments.models import WebhookEvent
from payments.application.commands import ExpireStalePaymentsCommand, ProcessWebhookCommand
from payments.helpers.encryption import encrypted_field_from_json
from payments.infrastructure.crypto import decrypt_field
from payments.infrastructure.factories import build_payment_command_handlers, build_payment_key_provider
from payments.infrastructure.retry_scheduler import CeleryRetryScheduler

logger = logging.getLogger(__name__)

RETRYABLE_WEBHOOK_STATUSES = {
    WebhookEvent.Status.PROCESSING,
    WebhookEvent.Status.LOCK_FAILED_RETRY,
    WebhookEvent.Status.VERIFY_FAILED_RETRY,
}

TERMINAL_WEBHOOK_STATUSES = {
    WebhookEvent.Status.PROCESSED_SUCCESS,
    WebhookEvent.Status.REJECTED_UNKNOWN,
    WebhookEvent.Status.REJECTED_POLICY,
    WebhookEvent.Status.FRAUD_DETECTED,
    WebhookEvent.Status.REJECTED_MISSING_REF,
}


def _decrypt_retry_payload(event: WebhookEvent, key_provider=None) -> dict:
    if not isinstance(event.payload, dict):
        raise ValueError(f"Webhook event {event.event_id} payload must be a JSON object")

    if {"ciphertext", "iv", "tag", "dek_encrypted"}.issubset(event.payload.keys()):
        if not event.dek_encrypted:
            raise ValueError(f"Webhook event {event.event_id} is missing encrypted payload metadata")

        if key_provider is None:
            key_provider = build_payment_key_provider()
        encrypted_payload = encrypted_field_from_json(event.payload)
        dek = key_provider.unwrap_dek(event.dek_encrypted)
        plain_bytes = decrypt_field(encrypted_payload, dek)
        return json.loads(plain_bytes.decode("utf-8"))

    return event.payload


def _load_retry_event(provider_reference: str) -> Tuple[Optional[WebhookEvent], Optional[dict]]:
    key_provider = build_payment_key_provider()
    candidates = WebhookEvent.objects.filter(
        status__in=list(RETRYABLE_WEBHOOK_STATUSES | TERMINAL_WEBHOOK_STATUSES)
    ).order_by("-created_at")

    for event in candidates:
        try:
            payload = _decrypt_retry_payload(event, key_provider)
        except Exception:
            logger.exception(
                "payment_webhook_retry_payload_decrypt_failed",
                extra={"event_id": event.event_id, "status": event.status},
            )
            continue

        if payload.get("data", {}).get("tx_ref") == provider_reference:
            return event, payload

    return None, None


@shared_task(bind=True, max_retries=3, name="payments.tasks.process_webhook_retry")
def process_webhook_retry(self, provider_reference: str):
    attempt = self.request.retries + 1
    logger.info(
        "payment_webhook_retry_started",
        extra={
            "provider_reference": provider_reference,
            "attempt": attempt,
            "task_id": getattr(self.request, "id", None),
        },
    )

    event, payload = _load_retry_event(provider_reference)
    if not event:
        logger.warning(
            "payment_webhook_retry_missing_event",
            extra={"provider_reference": provider_reference, "attempt": attempt},
        )
        CeleryRetryScheduler().reset_webhook_retry(provider_reference)
        return {"status": "missing_event", "provider_reference": provider_reference, "attempt": attempt}

    if event.status in TERMINAL_WEBHOOK_STATUSES:
        logger.info(
            "payment_webhook_retry_terminal_event",
            extra={
                "provider_reference": provider_reference,
                "event_id": event.event_id,
                "status": event.status,
                "attempt": attempt,
            },
        )
        CeleryRetryScheduler().reset_webhook_retry(provider_reference)
        return {
            "status": "terminal",
            "provider_reference": provider_reference,
            "event_id": event.event_id,
            "attempt": attempt,
        }

    if event.status not in RETRYABLE_WEBHOOK_STATUSES:
        logger.info(
            "payment_webhook_retry_non_retryable_status",
            extra={
                "provider_reference": provider_reference,
                "event_id": event.event_id,
                "status": event.status,
                "attempt": attempt,
            },
        )
        return {
            "status": "skipped",
            "reason": "non_retryable_status",
            "provider_reference": provider_reference,
            "event_id": event.event_id,
            "attempt": attempt,
        }

    handlers = build_payment_command_handlers()
    cmd = ProcessWebhookCommand(
        event_id=event.event_id,
        event_type=payload.get("event", ""),
        payload=payload,
        headers={},
        now=timezone.now(),
        encrypted_payload=None,
    )

    try:
        handlers._process_webhook(cmd, allow_existing_event=True)
    except Exception as exc:
        logger.exception(
            "payment_webhook_retry_handler_failed",
            extra={
                "provider_reference": provider_reference,
                "event_id": event.event_id,
                "attempt": attempt,
            },
        )
        if self.request.retries >= self.max_retries:
            CeleryRetryScheduler().reset_webhook_retry(provider_reference)
            raise

        raise self.retry(exc=exc, countdown=min(30 * (2 ** self.request.retries), 300))

    refreshed = WebhookEvent.objects.filter(event_id=event.event_id).first()
    final_status = refreshed.status if refreshed else event.status

    if final_status in TERMINAL_WEBHOOK_STATUSES:
        CeleryRetryScheduler().reset_webhook_retry(provider_reference)

    logger.info(
        "payment_webhook_retry_completed",
        extra={
            "provider_reference": provider_reference,
            "event_id": event.event_id,
            "final_status": final_status,
            "attempt": attempt,
        },
    )
    return {
        "status": "completed",
        "provider_reference": provider_reference,
        "event_id": event.event_id,
        "final_status": final_status,
        "attempt": attempt,
    }


@shared_task(name="payments.tasks.expire_stale_payments_task")
def expire_stale_payments_task():
    now = timezone.now()
    handlers = build_payment_command_handlers()
    count = handlers.expire_stale_payments(ExpireStalePaymentsCommand(now=now))
    return f"Expired {count} payments"
