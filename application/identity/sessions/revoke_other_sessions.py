"""Revoke every active session except the caller's current session."""

from dataclasses import dataclass
import uuid

from application.identity.shared.ports import SessionRepository, TokenFamilyRepository


@dataclass(frozen=True)
class RevokeOtherSessionsCommand:
    user_id: uuid.UUID | str
    current_session_id: uuid.UUID | str
    reason: str = "other_sessions_revoked"


@dataclass(frozen=True)
class RevokeOtherSessionsResult:
    revoked_count: int


class RevokeOtherSessionsUseCase:
    def __init__(
        self,
        *,
        session_repository: SessionRepository,
        token_family_repository: TokenFamilyRepository,
    ) -> None:
        self.session_repository = session_repository
        self.token_family_repository = token_family_repository

    def execute(self, cmd: RevokeOtherSessionsCommand) -> RevokeOtherSessionsResult:
        current_session_id = str(cmd.current_session_id)
        active_sessions = self.session_repository.list_active_identity_sessions(user_id=cmd.user_id)
        revoked_count = 0

        for session in active_sessions:
            session_id = str(session.id.value)
            if session_id == current_session_id:
                continue
            self.token_family_repository.blacklist_family(session.token_family.id)
            self.session_repository.revoke_identity_session(
                session_id=session_id,
                token_family=session.token_family.id,
                reason=cmd.reason,
            )
            revoked_count += 1

        return RevokeOtherSessionsResult(revoked_count=revoked_count)


__all__ = [
    "RevokeOtherSessionsCommand",
    "RevokeOtherSessionsResult",
    "RevokeOtherSessionsUseCase",
]
