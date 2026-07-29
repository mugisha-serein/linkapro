"""Command for updating account profile details."""

from dataclasses import dataclass
from typing import Optional
import uuid


@dataclass(frozen=True)
class UpdateProfileCommand:
    user_id: uuid.UUID
    first_name: Optional[str] = None
    last_name: Optional[str] = None


__all__ = ["UpdateProfileCommand"]
