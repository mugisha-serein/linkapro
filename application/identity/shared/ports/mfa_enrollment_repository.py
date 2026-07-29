"""MFA enrollment repository port."""

import uuid
from dataclasses import dataclass, field
from typing import Protocol

from domain.identity.mfa import MfaChallenge


@dataclass(frozen=True)
class MfaEnrollmentState:
    challenge: MfaChallenge
    secret: str = field(repr=False)


class MfaEnrollmentRepository(Protocol):
    def save(self, state: MfaEnrollmentState, *, ttl: int) -> None:
        ...

    def get(self, account_id: uuid.UUID) -> MfaEnrollmentState | None:
        ...

    def consume(self, account_id: uuid.UUID) -> None:
        ...


__all__ = ["MfaEnrollmentRepository", "MfaEnrollmentState"]
