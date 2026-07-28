"""MFA enrollment and replay storage ports."""

import uuid
from typing import Any, Protocol

from domain.identity.verification import VerificationCode


class MfaEnrollmentStore(Protocol):
    def save(self, user_id: uuid.UUID, state: Any, ttl: int) -> None:
        ...

    def get(self, user_id: uuid.UUID) -> Any | None:
        ...

    def consume(self, user_id: uuid.UUID) -> None:
        ...


class MfaReplayStore(Protocol):
    def has_been_used(self, challenge_id: uuid.UUID, token: VerificationCode) -> bool:
        ...

    def mark_used(self, challenge_id: uuid.UUID, token: VerificationCode, ttl: int) -> None:
        ...


__all__ = ["MfaEnrollmentStore", "MfaReplayStore"]
