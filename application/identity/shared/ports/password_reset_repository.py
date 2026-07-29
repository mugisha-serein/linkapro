"""Password-reset token and account persistence port."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
import uuid

from domain.identity.recovery import PasswordResetToken


@dataclass(frozen=True)
class PasswordResetVerification:
    user_id: uuid.UUID
    token: PasswordResetToken


class PasswordResetRepository(Protocol):
    def verify_reset_token(self, raw_token: str) -> PasswordResetVerification | None:
        ...

    def mark_token_expired(self, token: PasswordResetToken, *, now: datetime) -> None:
        ...

    def get_active_user_for_update(self, user_id: uuid.UUID):
        ...

    def persist_used_token(self, token: PasswordResetToken) -> None:
        ...

    def revoke_other_active_tokens(self, *, user, exclude_token_id: uuid.UUID, now: datetime) -> None:
        ...


__all__ = ["PasswordResetRepository", "PasswordResetVerification"]
