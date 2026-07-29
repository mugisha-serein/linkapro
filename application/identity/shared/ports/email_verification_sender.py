"""Email verification delivery port."""

from typing import Protocol

from domain.identity.verification import EmailVerificationToken


class EmailVerificationSender(Protocol):
    def send_email_verification(self, *, to: str, token: EmailVerificationToken) -> None:
        ...


__all__ = ["EmailVerificationSender"]
