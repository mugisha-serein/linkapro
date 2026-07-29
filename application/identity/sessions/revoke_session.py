"""Revoke a single named active session for an account."""

from dataclasses import dataclass
import uuid

from application.identity.shared.ports import SessionRepository, TokenFamilyRepository


@dataclass(frozen=True)
class RevokeSessionCommand:
    user_id: uuid.UUID | str
    session_id: uuid.UUID | str
    reason: str = "session_revoked"


@dataclass(frozen=True)
class RevokeSessionResult:
    revoked_count: int


class RevokeSessionUseCase:
    def __init__(
        self,
        *,
        session_repository: SessionRepository,
        token_family_repository: TokenFamilyRepository,
    ) -> None:
        self.session_repository = session_repository
        self.token_family_repository = token_family_repository

    def execute(self, cmd: RevokeSessionCommand) -> RevokeSessionResult:
        target_session_id = str(cmd.session_id)
        active_sessions = self.session_repository.list_active_identity_sessions(user_id=cmd.user_id)
        target_session = next(
            (session for session in active_sessions if str(session.id.value) == target_session_id),
            None,
        )
        if target_session is None:
            return RevokeSessionResult(revoked_count=0)

        self.token_family_repository.blacklist_family(target_session.token_family.id)
        self.session_repository.revoke_identity_session(
            session_id=target_session_id,
            token_family=target_session.token_family.id,
            reason=cmd.reason,
        )
        return RevokeSessionResult(revoked_count=1)


__all__ = ["RevokeSessionCommand", "RevokeSessionResult", "RevokeSessionUseCase"]
