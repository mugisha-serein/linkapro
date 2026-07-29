"""Step-up grant verification port."""

from __future__ import annotations

from typing import Protocol
import uuid


class StepUpGrantVerifier(Protocol):
    def verify(self, grant: str, *, user_id: uuid.UUID, purpose: str) -> bool:
        ...

    def consume(self, grant: str, *, user_id: uuid.UUID, purpose: str) -> None:
        ...


__all__ = ["StepUpGrantVerifier"]
