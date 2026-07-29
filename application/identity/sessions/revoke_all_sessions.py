"""Revoke every active identity session for an account."""

from dataclasses import dataclass
import uuid

from application.identity.shared.ports import SessionRepository, TokenFamilyRepository


@dataclass(frozen=True)
class RevokeAllSessionsResult:
    revoked_count: int


class RevokeAllSessionsUseCase:
    def __init__(
        self,
        *,
        session_repository: SessionRepository,
        token_family_repository: TokenFamilyRepository,
    ) -> None:
        self.session_repository = session_repository
        self.token_family_repository = token_family_repository

    def execute(
        self,
        *,
        user_id: uuid.UUID | str,
        reason: str = "all_sessions_revoked",
    ) -> RevokeAllSessionsResult:
        active_sessions = self.session_repository.list_active_identity_sessions(user_id=user_id)
        for session in active_sessions:
            self.token_family_repository.blacklist_family(session.token_family.id)
        revoked_count = self.session_repository.revoke_all_identity_sessions(
            user_id=user_id,
            reason=reason,
        )
        return RevokeAllSessionsResult(revoked_count=revoked_count)


__all__ = ["RevokeAllSessionsResult", "RevokeAllSessionsUseCase"]
