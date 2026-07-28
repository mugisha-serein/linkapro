"""Complete password reset for a verified reset token."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
import uuid

from domain.identity.credentials import (
    PasswordHash,
    PasswordHistory,
    PasswordPolicy,
    PlainPassword,
    UserPasswordChanged,
)
from domain.identity.recovery import (
    InvalidPasswordResetToken,
    PasswordReset,
    PasswordResetPolicy,
    PasswordResetToken,
    PasswordResetUserInactive,
)
from domain.identity.shared import SystemClock

from application.identity.commands import ResetPasswordCommand


@dataclass(frozen=True)
class PasswordResetVerification:
    user_id: uuid.UUID
    token: PasswordResetToken


class PasswordResetGateway(Protocol):
    def complete_in_transaction(self, operation): ...
    def verify_reset_token(self, raw_token: str) -> PasswordResetVerification | None: ...
    def mark_token_expired(self, token: PasswordResetToken, *, now: datetime) -> None: ...
    def get_active_user_for_update(self, user_id: uuid.UUID): ...
    def get_password_history(self, user) -> PasswordHistory: ...
    def password_matches(self, plain_password: PlainPassword, password_hash: PasswordHash) -> bool: ...
    def set_user_password(self, user, new_password: str) -> PasswordHash: ...
    def remember_password_hash(self, *, user, password_hash: PasswordHash, now: datetime) -> None: ...
    def persist_used_token(self, token: PasswordResetToken) -> None: ...
    def revoke_other_active_tokens(self, *, user, exclude_token_id: uuid.UUID, now: datetime) -> None: ...
    def dispatch_password_changed(self, event: UserPasswordChanged) -> None: ...
    def hash_reset_value(self, value: str) -> str: ...


@dataclass(frozen=True)
class PasswordResetResult:
    user_id: uuid.UUID


class ResetPasswordCommandHandler:
    def __init__(
        self,
        *,
        gateway: PasswordResetGateway,
        policy: PasswordResetPolicy | None = None,
        now=None,
    ):
        self.gateway = gateway
        self.policy = policy or PasswordResetPolicy()
        self.now = now or SystemClock().now

    def handle(self, cmd: ResetPasswordCommand) -> PasswordResetResult:
        return self.gateway.complete_in_transaction(lambda: self._handle_locked(cmd))

    def _handle_locked(self, cmd: ResetPasswordCommand) -> PasswordResetResult:
        now = self.now()
        verification = self.gateway.verify_reset_token(cmd.token)
        if not verification:
            raise InvalidPasswordResetToken("Invalid or expired reset token")

        try:
            self.policy.ensure_token_can_be_used(verification.token, now=now)
        except InvalidPasswordResetToken:
            if verification.token.is_expired(now=now):
                self.gateway.mark_token_expired(verification.token, now=now)
            raise

        user = self.gateway.get_active_user_for_update(verification.user_id)
        if not user:
            raise PasswordResetUserInactive("Invalid or expired reset token")

        plain_password = PlainPassword(cmd.new_password)
        PasswordPolicy.validate(plain_password)
        password_history = self.gateway.get_password_history(user)
        password_history.ensure_not_reused(plain_password, self.gateway.password_matches)
        new_password_hash = self.gateway.set_user_password(user, cmd.new_password)
        reset = PasswordReset(
            user_id=verification.user_id,
            token=verification.token,
            new_password_hash=new_password_hash,
            used_ip_hash=self.gateway.hash_reset_value(cmd.client_ip),
            used_user_agent_hash=self.gateway.hash_reset_value(cmd.user_agent),
        )
        used_token = reset.consume_token(policy=self.policy, now=now)
        self.gateway.remember_password_hash(
            user=user,
            password_hash=new_password_hash,
            now=now,
        )
        self.gateway.dispatch_password_changed(
            UserPasswordChanged(
                user_id=verification.user_id,
                occurred_at=now,
                reason="credential_recovery",
            )
        )
        self.gateway.persist_used_token(used_token)
        self.gateway.revoke_other_active_tokens(
            user=user,
            exclude_token_id=used_token.id,
            now=now,
        )
        return PasswordResetResult(user_id=verification.user_id)


__all__ = [
    "PasswordResetGateway",
    "PasswordResetResult",
    "PasswordResetVerification",
    "ResetPasswordCommandHandler",
]
