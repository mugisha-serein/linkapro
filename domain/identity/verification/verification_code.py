"""Verification code value object."""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import hmac
import secrets

from .verification_errors import InvalidVerificationCode


@dataclass(frozen=True)
class VerificationCode:
    value: str = field(repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.value, str):
            raise InvalidVerificationCode("Verification code must be text")
        normalized = self.value.strip()
        if not normalized:
            raise InvalidVerificationCode("Verification code is required")
        if normalized != self.value:
            raise InvalidVerificationCode("Verification code cannot have leading or trailing whitespace")
        if any(ord(character) < 32 for character in normalized):
            raise InvalidVerificationCode("Verification code cannot contain control characters")
        if len(normalized) > 4096:
            raise InvalidVerificationCode("Verification code is too long")

    @classmethod
    def generate_numeric(cls, digits: int = 6) -> "VerificationCode":
        if digits <= 0:
            raise InvalidVerificationCode("Verification code length must be positive")
        upper_bound = 10**digits
        return cls(f"{secrets.randbelow(upper_bound):0{digits}d}")

    @property
    def digest(self) -> str:
        return hashlib.sha256(self.value.encode("utf-8")).hexdigest()

    def matches_digest(self, digest: str) -> bool:
        return hmac.compare_digest(self.digest, digest)
