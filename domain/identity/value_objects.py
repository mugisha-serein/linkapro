"""Immutable value objects for identity."""
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

    MAX_LENGTH = 128

    def __post_init__(self) -> None:
        if not self.value:
            raise WeakPasswordError("Password cannot be empty")
        if len(self.value) > self.MAX_LENGTH:
            raise WeakPasswordError("Password cannot be longer than 128 characters")
        if any(self._is_unsafe_control_character(char) for char in self.value):
            raise WeakPasswordError("Password cannot contain unsafe control characters")

    @staticmethod
    def _is_unsafe_control_character(char: str) -> bool:
        return ord(char) < 32 or ord(char) == 127

    def reveal_for_password_hashing(self) -> str:
        """Return the raw password only for the explicit password-hashing purpose."""
        return self.value

    def __str__(self) -> str:
        return "******"  # Never expose plain password

    def __repr__(self) -> str:
        return "PlainPassword(value='******')"


@dataclass(frozen=True, repr=False)
class ApprovedPasswordChange:
    """A password hash that has passed the domain password-change checks."""
    new_password_hash: PasswordHash
    blocklist_checked: bool
    reuse_checked: bool
    reuse_check_required: bool = True

    def __post_init__(self) -> None:
        if not self.blocklist_checked:
            raise ValueError("Password blocklist check must be completed")
        if self.reuse_check_required and not self.reuse_checked:
            raise ValueError("Password reuse check must be completed")

    def __repr__(self) -> str:
        return (
            "ApprovedPasswordChange("
            "new_password_hash='******', "
            f"blocklist_checked={self.blocklist_checked}, "
            f"reuse_checked={self.reuse_checked}, "
            f"reuse_check_required={self.reuse_check_required})"
        )
    
@dataclass(frozen=True)
class TOTPSecret:
    """Base32‑encoded TOTP secret."""
    value: str

    def __post_init__(self):
        if not re.match(r'^[A-Z2-7]+=*$', self.value):
            raise ValueError("Invalid TOTP secret format")

    def __str__(self) -> str:
        return self.value
