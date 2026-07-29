"""Command for completing MFA login."""

from dataclasses import dataclass, field

from domain.identity.verification import VerificationCode


@dataclass(frozen=True)
class LoginTwoFactorCommand:
    temp_token: str = field(repr=False)
    token: VerificationCode = field(repr=False)


__all__ = ["LoginTwoFactorCommand"]
