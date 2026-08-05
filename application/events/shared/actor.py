import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class EventActor:
    user_id: uuid.UUID

