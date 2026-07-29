"""MFA challenge repository port."""

from typing import Protocol
import uuid

from domain.identity.mfa import MfaChallenge


class MfaChallengeRepository(Protocol):
    def save(self, challenge: MfaChallenge) -> None:
        ...

    def get(self, challenge_id: uuid.UUID) -> MfaChallenge | None:
        ...


__all__ = ["MfaChallengeRepository"]
