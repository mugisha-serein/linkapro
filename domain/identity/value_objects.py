"""Immutable value objects for identity."""
import base64
import binascii
import re
from dataclasses import dataclass
from enum import Enum


class InvalidEmailError(ValueError):
    pass


class WeakPasswordError(ValueError):
    pass


class OAuthProvider(str, Enum):
    GOOGLE = "google"


@dataclass(frozen=True)
class SecretValue:
    """Sensitive string value that is safe by default in logs and reprs."""
    value: str

    def __post_init__(self) -> None:
        if not self.value or not self.value.strip():
            raise ValueError("Secret value cannot be empty")

    @property
    def raw_value(self) -> str:
        return self.value

    def reveal(self) -> str:
        return self.value

    def __str__(self) -> str:
        return "******"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(value='******')"


class OAuthAccessToken(SecretValue):
    """OAuth access token. Raw value access must be explicit."""


class OAuthRefreshToken(SecretValue):
    """OAuth refresh token. Raw value access must be explicit."""


@dataclass(frozen=True)
class Email:
    """Validated email address value object."""
    value: str

    def __post_init__(self) -> None:
        normalized = self.value.strip().lower()
        object.__setattr__(self, "value", normalized)
        if not self._is_valid(normalized):
            raise InvalidEmailError("Invalid email")

    @staticmethod
    def _is_valid(email: str) -> bool:
        pattern = r"^[a-z0-9_.+-]+@[a-z0-9-]+\.[a-z0-9-.]+$"
        return re.match(pattern, email) is not None

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class PasswordHash:
    """Hashed password value object. The hash is created by the infrastructure layer."""
    value: str

    def __post_init__(self) -> None:
        if not self.value:
            raise ValueError("Password hash cannot be empty")

    @property
    def raw_value(self) -> str:
        return self.value

    def reveal(self) -> str:
        return self.value

    def __str__(self) -> str:
        return "******"

    def __repr__(self) -> str:
        return "PasswordHash(value='******')"


@dataclass(frozen=True)
class PlainPassword:
    """Plain-text password used only during registration/password change. Never stored."""
    value: str

    def __post_init__(self) -> None:
        if self.value != self.value.strip():
            raise WeakPasswordError("Password cannot start or end with whitespace")
        if len(self.value) < 8:
            raise WeakPasswordError("Password must be at least 8 characters long")
        if len(self.value) > 128:
            raise WeakPasswordError("Password must be at most 128 characters long")
        if not re.search(r"[A-Z]", self.value):
            raise WeakPasswordError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", self.value):
            raise WeakPasswordError("Password must contain at least one lowercase letter")
        if not re.search(r"\d", self.value):
            raise WeakPasswordError("Password must contain at least one digit")
        if not re.search(r"[^A-Za-z0-9\s]", self.value):
            raise WeakPasswordError(
                "Password must contain at least one non-whitespace special character"
            )

    def __str__(self) -> str:
        return "******"

    def __repr__(self) -> str:
        return "PlainPassword(value='******')"
    
@dataclass(frozen=True)
class TOTPSecret:
    """Base32‑encoded TOTP secret."""
    value: str

    def __post_init__(self):
        normalized = self.value.strip().upper()
        object.__setattr__(self, "value", normalized)
        unpadded = normalized.rstrip("=")
        if len(unpadded) < 16:
            raise ValueError("TOTP secret must be at least 16 characters long")
        if not re.match(r'^[A-Z2-7]+=*$', normalized):
            raise ValueError("Invalid TOTP secret format")
        try:
            base64.b32decode(normalized, casefold=False)
        except (binascii.Error, ValueError):
            raise ValueError("Invalid TOTP secret format") from None

    @property
    def raw_value(self) -> str:
        return self.value

    def reveal(self) -> str:
        return self.value

    def reveal_for_totp_verification(self) -> str:
        return self.value

    def __str__(self) -> str:
        return "******"

    def __repr__(self) -> str:
        return "TOTPSecret(value='******')"
