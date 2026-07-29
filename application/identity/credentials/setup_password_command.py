"""Command for setting up an account password."""

from dataclasses import dataclass, field
import uuid

from domain.identity.credentials import PlainPassword


@dataclass(frozen=True)
class SetupPasswordCommand:
    user_id: uuid.UUID
    plain_password: PlainPassword = field(repr=False)


__all__ = ["SetupPasswordCommand"]
