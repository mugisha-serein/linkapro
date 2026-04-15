# No Business Logic Here
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class GetProfileCommand:
    user_id: str


@dataclass(slots=True)
class GetProfileResult:
    success: bool
    user: Any | None = None
    failure_reason: str | None = None


@dataclass(slots=True)
class UpdateProfileCommand:
    user_id: str
    email: str | None = None
    role: str | None = None
    is_active: bool | None = None


@dataclass(slots=True)
class UpdateProfileResult:
    success: bool
    user: Any | None = None
    failure_reason: str | None = None
    changes_made: list[str] | None = None