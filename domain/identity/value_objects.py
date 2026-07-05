"""Immutable value objects for identity."""
import base64
import binascii
import re
from dataclasses import dataclass
from enum import Enum
from typing import ClassVar


class InvalidEmailError(ValueError):
    pass


class WeakPasswordError(ValueError):
    pass


class InvalidSecurityReasonError(ValueError):
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

    def reveal_for_provider_sync(self) -> str:
        return self.value


class OAuthRefreshToken(SecretValue):
    """OAuth refresh token. Raw value access must be explicit."""

    def reveal_for_provider_sync(self) -> str:
        return self.value


@dataclass(frozen=True)
class PersonName:
    """Person name used by the identity domain."""
    first_name: str
    last_name: str

    def __post_init__(self) -> None:
        first_name = self.first_name.strip()
        last_name = self.last_name.strip()
        if not first_name:
            raise ValueError("First name cannot be empty")
        if not last_name:
            raise ValueError("Last name cannot be empty")
        object.__setattr__(self, "first_name", first_name)
        object.__setattr__(self, "last_name", last_name)

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"


@dataclass(frozen=True)
class SecurityReason:
    """Human-readable security context that must not carry secrets."""
    value: str

    _FORBIDDEN_FRAGMENTS: ClassVar[tuple[str, ...]] = (
        "password",
        "token",
        "secret",
        "totp",
        "refresh",
    )

    def __post_init__(self) -> None:
        normalized = self.value.strip()
        if not normalized:
            raise InvalidSecurityReasonError("Security reason cannot be empty")
        lowered = normalized.lower()
        if any(fragment in lowered for fragment in self._FORBIDDEN_FRAGMENTS):
            raise InvalidSecurityReasonError("Security reason cannot contain secret-like text")
        object.__setattr__(self, "value", normalized)

    def __str__(self) -> str:
        return self.value


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

    def reveal_for_password_verification(self) -> str:
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
