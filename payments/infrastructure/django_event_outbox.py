from __future__ import annotations

from dataclasses import asdict, is_dataclass
import json
import uuid

from django.core.serializers.json import DjangoJSONEncoder
from django.db import IntegrityError, transaction

from django_app.payments.models import PaymentDomainEventOutbox


class DjangoPaymentEventOutboxDispatcher:
    """Durably insert payment domain events and schedule publication after commit."""

    def dispatch(self, event) -> None:
        self._validate_event(event)
        payload = self._event_payload(event)

        try:
            # A nested atomic block gives this insert its own savepoint. A duplicate
            # event_id can then be inspected safely without breaking an enclosing UoW.
            with transaction.atomic():
                outbox = PaymentDomainEventOutbox.objects.create(
                    event_id=event.event_id,
                    aggregate_id=event.payment_id,
                    aggregate_version=0,
                    event_type=type(event).__name__,
                    occurred_at=event.occurred_at,
                    payload=payload,
                )
        except IntegrityError:
            if PaymentDomainEventOutbox.objects.filter(event_id=event.event_id).exists():
                return
            raise

        transaction.on_commit(lambda event_id=outbox.id: self._schedule(event_id))

    @staticmethod
    def _validate_event(event) -> None:
        required = ("event_id", "payment_id", "occurred_at")
        missing = [name for name in required if getattr(event, name, None) is None]
        if missing:
            raise ValueError(f"Pending payment event is missing: {', '.join(missing)}.")

    @staticmethod
    def _event_payload(event) -> dict:
        payload = asdict(event) if is_dataclass(event) else dict(vars(event))
        return json.loads(json.dumps(payload, cls=DjangoJSONEncoder, default=str))

    @staticmethod
    def _schedule(event_id: uuid.UUID) -> None:
        try:
            from tasks.payment_domain_events import publish_payment_domain_event_task

            publish_payment_domain_event_task.delay(str(event_id))
        except Exception:
            # The durable row remains pending; the retry worker is the recovery path.
            return
