# domain/value_objects/__init__.py
# Pure Python — no framework, no ORM, no I/O

from __future__ import annotations

import re
import uuid
import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, unique
from typing import Optional

from domain.exceptions import (
    InvalidEmailError,
    InvalidPasswordError,
    InvalidFingerprintError,
)


# ══════════════════════════════════════════════════════════
# ENUMERATIONS
# ══════════════════════════════════════════════════════════

@unique
class RoleType(Enum):
    """Exhaustive set of supported roles in the marketplace platform."""
    USER   = "USER"
    VENDOR = "VENDOR"
    ADMIN  = "ADMIN"


@unique
class SessionStatus(Enum):
    """Lifecycle states a Session may occupy."""
    ACTIVE  = "ACTIVE"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"


@unique
class LoginOutcome(Enum):
    """All possible outcomes recorded in a LoginActivity log entry."""
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    BLOCKED = "BLOCKED"


@unique
class TokenStatus(Enum):
    """Lifecycle states for a RefreshToken."""
    ACTIVE    = "ACTIVE"
    USED      = "USED"       # consumed by rotation; a successor exists
    REVOKED   = "REVOKED"    # invalidated (reuse detected or logout)
    EXPIRED   = "EXPIRED"


# ══════════════════════════════════════════════════════════
# IMMUTABLE VALUE OBJECTS
# All are frozen dataclasses — equality is by value, not identity.
# ══════════════════════════════════════════════════════════

@dataclass(frozen=True)
class Email:
    """
    Canonical, normalised email address.
    Validates format on construction; stored lower-cased.
    """
    address: str

    _PATTERN: re.Pattern = field(
        default=re.compile(r"^[a-zA-Z0-9_.+\-]+@[a-zA-Z0-9\-]+\.[a-zA-Z0-9.\-]+$"),
        init=False, repr=False, compare=False,
    )

    def __post_init__(self) -> None:
        normalised = self.address.strip().lower()
        # bypass frozen restriction for the single normalisation step
        object.__setattr__(self, "address", normalised)
        if not self._PATTERN.match(normalised):
            raise InvalidEmailError(f"'{self.address}' is not a valid email address.")

    def __str__(self) -> str:
        return self.address


@dataclass(frozen=True)
class HashedPassword:
    """
    Represents a password that has already been hashed by the application layer.
    The domain never handles plaintext passwords.

    Rules enforced:
    - Value must not be blank.
    - Value must have minimum expected hash length (64 chars for SHA-256 hex or bcrypt).
    """
    value: str

    _MIN_LENGTH: int = field(default=60, init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        if not self.value or not self.value.strip():
            raise InvalidPasswordError("Hashed password must not be empty.")
        if len(self.value) < self._MIN_LENGTH:
            raise InvalidPasswordError(
                f"Hashed password appears too short "
                f"(minimum {self._MIN_LENGTH} characters expected)."
            )

    def matches(self, other_hash: str) -> bool:
        """Constant-time comparison to prevent timing attacks."""
        return hashlib.compare_digest(self.value, other_hash)


@dataclass(frozen=True)
class DeviceFingerprintValue:
    """
    A normalised, deterministic fingerprint string derived from device
    attributes (UA, screen, timezone, etc.).  The domain treats it as
    an opaque token — it never trusted, only tracked.

    Rules:
    - Must not be blank.
    - Normalised to lower-case hex; invalid chars rejected.
    """
    raw: str

    _PATTERN: re.Pattern = field(
        default=re.compile(r"^[a-f0-9]{32,128}$"),
        init=False, repr=False, compare=False,
    )

    def __post_init__(self) -> None:
        normalised = self.raw.strip().lower()
        object.__setattr__(self, "raw", normalised)
        if not self._PATTERN.match(normalised):
            raise InvalidFingerprintError(
                "Device fingerprint must be a 32–128 character hex string."
            )

    def __str__(self) -> str:
        return self.raw


@dataclass(frozen=True)
class TokenFamilyId:
    """
    Opaque identifier grouping all rotation-chain tokens for a single session.
    Compromise of any member → entire family revoked.
    """
    value: str

    def __post_init__(self) -> None:
        if not self.value or not self.value.strip():
            raise ValueError("TokenFamilyId must not be empty.")

    @classmethod
    def generate(cls) -> "TokenFamilyId":
        return cls(value=str(uuid.uuid4()))

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class UserId:
    """Strongly-typed user identifier (UUID)."""
    value: str

    def __post_init__(self) -> None:
        try:
            uuid.UUID(self.value)
        except ValueError:
            raise ValueError(f"UserId '{self.value}' is not a valid UUID.")

    @classmethod
    def generate(cls) -> "UserId":
        return cls(value=str(uuid.uuid4()))

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class SessionId:
    """Strongly-typed session identifier (UUID)."""
    value: str

    def __post_init__(self) -> None:
        try:
            uuid.UUID(self.value)
        except ValueError:
            raise ValueError(f"SessionId '{self.value}' is not a valid UUID.")

    @classmethod
    def generate(cls) -> "SessionId":
        return cls(value=str(uuid.uuid4()))

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class TokenId:
    """Strongly-typed token identifier (UUID)."""
    value: str

    def __post_init__(self) -> None:
        try:
            uuid.UUID(self.value)
        except ValueError:
            raise ValueError(f"TokenId '{self.value}' is not a valid UUID.")

    @classmethod
    def generate(cls) -> "TokenId":
        return cls(value=str(uuid.uuid4()))

    def __str__(self) -> str:
        return self.value


def utc_now() -> datetime:
    """Domain-wide UTC timestamp factory — single source of truth."""
    return datetime.now(tz=timezone.utc)