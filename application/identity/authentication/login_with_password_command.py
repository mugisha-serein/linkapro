"""Command for password login."""

from dataclasses import dataclass, field

from domain.identity.credentials import Email, PlainPassword


@dataclass(frozen=True)
class LoginUserCommand:
    email: Email
    plain_password: PlainPassword = field(repr=False)


__all__ = ["LoginUserCommand"]
