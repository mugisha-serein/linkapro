"""Complete password reset for a verified reset token."""
from __future__ import annotations

from dataclasses import dataclass
import uuid

from domain.identity.credentials import (
    PasswordHash,
    PasswordPolicy,
)
from domain.identity.recovery import (
    InvalidPasswordResetToken,
    PasswordReset,
    PasswordResetPolicy,
    PasswordResetUserInactive,
)
from domain.identity.shared import SystemClock

from application.identity.recovery.reset_password_command import ResetPasswordCommand
from application.identity.sessions import RevokeAllSessionsUseCase
from application.identity.shared.ports import (
    AccountRepository,
    EventOutbox,
    IdentityUnitOfWork,
    PasswordHasher,
    PasswordHistoryRepository,
    PasswordResetRepository,
    PasswordResetVerification,
)


@dataclass(frozen=True)
class PasswordResetResult:
    user_id: uuid.UUID


class ResetPasswordCommandHandler:
    def __init__(
        self,
        *,
        account_repository: AccountRepository,
        password_reset_repository: PasswordResetRepository,
        password_history_repository: PasswordHistoryRepository,
        password_hasher: PasswordHasher,
        event_outbox: EventOutbox,
        revoke_all_sessions_use_case: RevokeAllSessionsUseCase,
        unit_of_work: IdentityUnitOfWork,
        policy: PasswordResetPolicy | None = None,
        now=None,
    ):
        self.account_repository = account_repository
        self.password_reset_repository = password_reset_repository
        self.password_history_repository = password_history_repository
        self.password_hasher = password_hasher
        self.event_outbox = event_outbox
        self.revoke_all_sessions_use_case = revoke_all_sessions_use_case
        self.unit_of_work = unit_of_work
        self.policy = policy or PasswordResetPolicy()
        self.now = now or SystemClock().now

    def handle(self, cmd: ResetPasswordCommand) -> PasswordResetResult:
        with self.unit_of_work as unit_of_work:
            result = self._handle_locked(cmd)
            unit_of_work.commit()
            return result

    def _handle_locked(self, cmd: ResetPasswordCommand) -> PasswordResetResult:
        now = self.now()
        verification = self.password_reset_repository.verify_reset_token(
            cmd.token.reveal_for_password_reset()
        )
        if not verification:
            raise InvalidPasswordResetToken("Invalid or expired reset token")

        try:
            self.policy.ensure_token_can_be_used(verification.token, now=now)
        except InvalidPasswordResetToken:
            if verification.token.is_expired(now=now):
                self.password_reset_repository.mark_token_expired(verification.token, now=now)
            raise

        locked_user = self.password_reset_repository.get_active_user_for_update(verification.user_id)
        if not locked_user:
            raise PasswordResetUserInactive("Invalid or expired reset token")
        user = self.account_repository.get_by_id(verification.user_id)
        if not user or not user.is_active:
            raise PasswordResetUserInactive("Invalid or expired reset token")

        PasswordPolicy.validate(cmd.new_password)
        password_history = self.password_history_repository.get_password_history(user)
        new_password_hash = PasswordHash(self.password_hasher.hash(cmd.new_password))
        user.change_password(
            new_password_hash,
            now=now,
            plain_password=cmd.new_password,
            password_history=password_history,
            password_verifier=self.password_hasher.verify,
        )
        reset = PasswordReset(
            user_id=verification.user_id,
            token=verification.token,
            new_password_hash=new_password_hash,
            used_ip_hash=cmd.client_ip_hash.value,
            used_user_agent_hash=cmd.user_agent_hash.value,
        )
        used_token = reset.consume_token(policy=self.policy, now=now)
        self.account_repository.save(user)
        for event in user.pull_events():
            self.event_outbox.dispatch(event)
        self.revoke_all_sessions_use_case.execute(
            user_id=verification.user_id,
            reason="password_reset",
        )
        self.password_reset_repository.persist_used_token(used_token)
        self.password_reset_repository.revoke_other_active_tokens(
            user=user,
            exclude_token_id=used_token.id,
            now=now,
        )
        return PasswordResetResult(user_id=verification.user_id)


__all__ = [
    "PasswordResetResult",
    "PasswordResetVerification",
    "ResetPasswordCommandHandler",
]
