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
        if not self._is_valid(self.value):
            raise InvalidEmailError(f"Invalid email: {self.value}")

    @staticmethod
    def _is_valid(email: str) -> bool:
        pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
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
        return self.value


@dataclass(frozen=True)
class PlainPassword:
    """Plain-text password used only during registration/password change. Never stored."""
    value: str

    def __post_init__(self) -> None:
        if len(self.value) < 8:
            raise WeakPasswordError("Password must be at least 8 characters long")
        if not re.search(r"[A-Z]", self.value):
            raise WeakPasswordError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", self.value):
            raise WeakPasswordError("Password must contain at least one lowercase letter")
        if not re.search(r"\d", self.value):
            raise WeakPasswordError("Password must contain at least one digit")

    def __str__(self) -> str:
        return "******"  # Never expose plain password
    
@dataclass(frozen=True)
class TOTPSecret:
    """Base32‑encoded TOTP secret."""
    value: str

    def __post_init__(self):
        if not re.match(r'^[A-Z2-7]+=*$', self.value):
            raise ValueError("Invalid TOTP secret format")

    def __str__(self) -> str:
        return self.value