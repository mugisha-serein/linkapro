"""MFA enrollment and replay storage ports."""

import uuid
from typing import Protocol

from domain.identity.verification import VerificationCode


class MfaReplayStore(Protocol):
    def has_been_used(self, challenge_id: uuid.UUID, token: VerificationCode) -> bool:
        ...

    def mark_used(self, challenge_id: uuid.UUID, token: VerificationCode, ttl: int) -> None:
        ...


__all__ = ["MfaReplayStore"]
