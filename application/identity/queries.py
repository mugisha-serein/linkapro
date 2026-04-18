"""Query objects for identity read operations."""
from dataclasses import dataclass
import uuid

from domain.identity.value_objects import Email


@dataclass(frozen=True)
class GetUserByIdQuery:
    user_id: uuid.UUID


@dataclass(frozen=True)
class GetUserByEmailQuery:
    email: Email