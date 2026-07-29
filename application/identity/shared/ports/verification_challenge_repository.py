"""Verification challenge persistence port."""

from typing import Protocol
import uuid

from domain.identity.verification import VerificationChallenge


class VerificationChallengeRepository(Protocol):
    def save(self, challenge: VerificationChallenge) -> None:
        ...

    def get(self, challenge_id: uuid.UUID) -> VerificationChallenge | None:
        ...


__all__ = ["VerificationChallengeRepository"]
