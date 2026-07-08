from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime
from decimal import Decimal
import uuid

from django.core.serializers.json import DjangoJSONEncoder
from django.db import IntegrityError, transaction
import json

from django_app.vendors.models import VendorDomainEventOutbox


class DjangoVendorEventOutboxDispatcher:
    def dispatch(self, event) -> None:
        payload = self._event_payload(event)
        try:
            outbox = VendorDomainEventOutbox.objects.create(
                event_id=event.event_id,
                aggregate_id=event.aggregate_id,
                aggregate_version=event.aggregate_version,
                event_type=type(event).__name__,
                occurred_at=event.occurred_at,
                payload=payload,
            )
        except IntegrityError:
            return
        transaction.on_commit(lambda event_id=outbox.id: self._schedule(event_id))

    @staticmethod
    def _event_payload(event) -> dict:
        payload = asdict(event) if is_dataclass(event) else dict(vars(event))
        return json.loads(json.dumps(payload, cls=DjangoJSONEncoder, default=str))

    @staticmethod
    def _schedule(event_id: uuid.UUID) -> None:
        try:
            from tasks.vendor_domain_events import publish_vendor_domain_event_task

            publish_vendor_domain_event_task.delay(str(event_id))
        except Exception:
            # The durable row is the source of truth; retry beat can pick it up.
            return
