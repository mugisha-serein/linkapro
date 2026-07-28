"""pyotp-backed TOTP service."""

from datetime import datetime

import pyotp

from application.identity.shared.ports import TotpService
from domain.identity.mfa import TOTPSecret
from domain.identity.verification import VerificationCode


class PyotpTotpService(TotpService):
    def generate_secret(self) -> str:
        return pyotp.random_base32()

    def provisioning_uri(self, secret: str, *, name: str, issuer_name: str) -> str:
        return pyotp.TOTP(secret).provisioning_uri(name=name, issuer_name=issuer_name)

    def verify(self, secret: TOTPSecret, token: VerificationCode, *, now: datetime) -> bool:
        return pyotp.TOTP(secret.reveal_for_totp_verification()).verify(token.value, for_time=now)


__all__ = ["PyotpTotpService"]
