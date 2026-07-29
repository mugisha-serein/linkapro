"""Command for changing an authenticated account password."""

from dataclasses import dataclass, field
import uuid

from domain.identity.credentials import PlainPassword


@dataclass(frozen=True)
class ChangePasswordCommand:
    user_id: uuid.UUID
    current_password: PlainPassword = field(repr=False)
    new_password: PlainPassword = field(repr=False)


__all__ = ["ChangePasswordCommand"]
