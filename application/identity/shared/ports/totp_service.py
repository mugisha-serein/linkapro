"""TOTP operations port for identity application services."""

from datetime import datetime
from typing import Protocol

from domain.identity.mfa import TOTPSecret
from domain.identity.verification import VerificationCode


class TotpService(Protocol):
    def generate_secret(self) -> str:
        ...

    def provisioning_uri(self, secret: str, *, name: str, issuer_name: str) -> str:
        ...

    def verify(self, secret: TOTPSecret, token: VerificationCode, *, now: datetime) -> bool:
        ...


__all__ = ["TotpService"]
