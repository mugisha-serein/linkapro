"""Query objects for identity read operations."""
from dataclasses import dataclass
import uuid


@dataclass(frozen=True)
class GetUserByIdQuery:
    user_id: uuid.UUID
