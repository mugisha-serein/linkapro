"""Immutable value objects for identity."""
import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class InvalidEmailError(ValueError):
    pass


class WeakPasswordError(ValueError):
    pass


class OAuthProvider(str, Enum):
    GOOGLE = "google"


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

    def __str__(self) -> str:
        return "******"

    def __repr__(self) -> str:
        return "PasswordHash(value='******')"


@dataclass(frozen=True)
class PlainPassword:
    """Plain-text password used only during registration/password change. Never stored."""
    value: str

    def __post_init__(self) -> None:
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
        if not re.search(r"[^A-Za-z0-9]", self.value):
            raise WeakPasswordError("Password must contain at least one special character")

    def __str__(self) -> str:
        return "******"

    def __repr__(self) -> str:
        return "PlainPassword(value='******')"
    
@dataclass(frozen=True)
class TOTPSecret:
    """Base32‑encoded TOTP secret."""
    value: str

    def __post_init__(self):
        if not re.match(r'^[A-Z2-7]+=*$', self.value):
            raise ValueError("Invalid TOTP secret format")

    @property
    def raw_value(self) -> str:
        return self.value

    def reveal(self) -> str:
        return self.value

    def __str__(self) -> str:
        return "******"

    def __repr__(self) -> str:
        return "TOTPSecret(value='******')"
