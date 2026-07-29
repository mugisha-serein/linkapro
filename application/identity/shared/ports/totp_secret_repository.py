"""TOTP secret persistence port."""

from abc import ABC, abstractmethod
from typing import Optional
import uuid

from domain.identity.mfa import TOTPSecret


class TotpSecretRepository(ABC):
    @abstractmethod
    def set_totp_secret(self, user_id: uuid.UUID, secret: TOTPSecret) -> None:
        """Persist the user's TOTP secret."""

    @abstractmethod
    def get_totp_secret(self, user_id: uuid.UUID) -> Optional[TOTPSecret]:
        """Retrieve the user's TOTP secret."""

    @abstractmethod
    def clear_totp_secret(self, user_id: uuid.UUID) -> None:
        """Clear the user's TOTP secret."""


__all__ = ["TotpSecretRepository"]
