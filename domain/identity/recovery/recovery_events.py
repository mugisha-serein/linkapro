"""Recovery-domain events."""
from dataclasses import dataclass
import uuid

from domain.identity.credentials import Email
from domain.identity.shared import DomainEvent


@dataclass(frozen=True)
class PasswordResetRequested(DomainEvent):
    user_id: uuid.UUID
    email: Email
    delivery_id: uuid.UUID
