"""Command for registering an identity account."""

from dataclasses import dataclass, field

from domain.identity.account import AccountRole
from domain.identity.credentials import Email, PlainPassword


@dataclass(frozen=True)
class RegisterUserCommand:
    email: Email
    plain_password: PlainPassword = field(repr=False)
    first_name: str
    last_name: str
    role: AccountRole


__all__ = ["RegisterUserCommand"]
