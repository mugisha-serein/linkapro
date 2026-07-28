"""Password reset policy."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .password_reset_token import PasswordResetToken, PasswordResetTokenStatus
from .recovery_errors import (
    InvalidPasswordResetToken,
    PasswordResetAlreadyUsed,
    PasswordResetExpired,
    PasswordResetUserInactive,
)


@dataclass(frozen=True)
class PasswordResetPolicy:
    def ensure_token_can_be_used(self, token: PasswordResetToken, *, now: datetime) -> None:
        if token.status is not PasswordResetTokenStatus.ACTIVE:
            if token.status is PasswordResetTokenStatus.USED:
                raise PasswordResetAlreadyUsed("Invalid or expired reset token")
            raise InvalidPasswordResetToken("Invalid or expired reset token")
        if token.is_expired(now=now):
            raise PasswordResetExpired("Invalid or expired reset token")

    def ensure_user_can_reset_password(self, *, user_is_active: bool) -> None:
        if not user_is_active:
            raise PasswordResetUserInactive("Invalid or expired reset token")

    def consume_token(
        self,
        token: PasswordResetToken,
        *,
        now: datetime,
        used_ip_hash: str | None,
        used_user_agent_hash: str | None,
    ) -> PasswordResetToken:
        self.ensure_token_can_be_used(token, now=now)
        return token.mark_used(
            now=now,
            used_ip_hash=used_ip_hash,
            used_user_agent_hash=used_user_agent_hash,
        )
