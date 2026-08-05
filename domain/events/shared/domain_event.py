"""Shared event-domain event primitives."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime

from domain.shared.utils import utc_now


@dataclass(frozen=True)
class DomainEvent:
    event_id: uuid.UUID = field(default_factory=uuid.uuid4)
    occurred_at: datetime = field(default_factory=utc_now)

