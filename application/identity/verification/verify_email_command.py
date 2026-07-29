"""Command for verifying an email address."""

from dataclasses import dataclass, field

from domain.identity.verification import EmailVerificationToken


@dataclass(frozen=True)
class VerifyEmailCommand:
    verification_token: EmailVerificationToken = field(repr=False)


__all__ = ["VerifyEmailCommand"]
