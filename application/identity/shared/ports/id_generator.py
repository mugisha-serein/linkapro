"""ID generation port for identity application services."""

import uuid
from typing import Protocol


class IdGenerator(Protocol):
    def new_id(self) -> uuid.UUID:
        ...


__all__ = ["IdGenerator"]
