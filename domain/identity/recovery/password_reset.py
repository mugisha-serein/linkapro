"""Password reset workflow model."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import uuid

from domain.identity.credentials import PasswordHash

from .password_reset_policy import PasswordResetPolicy
from .password_reset_token import PasswordResetToken


@dataclass(frozen=True)
class PasswordReset:
    user_id: uuid.UUID
    token: PasswordResetToken
    new_password_hash: PasswordHash
    used_ip_hash: str | None
    used_user_agent_hash: str | None

    def consume_token(self, *, policy: PasswordResetPolicy, now: datetime) -> PasswordResetToken:
        return policy.consume_token(
            self.token,
            now=now,
            used_ip_hash=self.used_ip_hash,
            used_user_agent_hash=self.used_user_agent_hash,
        )
