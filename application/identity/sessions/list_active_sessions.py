"""List active identity sessions for an account."""

from dataclasses import dataclass
import uuid

from application.identity.shared.ports import SessionRepository
from domain.identity.sessions import IdentitySession


@dataclass(frozen=True)
class ActiveSessionDTO:
    session_id: str
    token_family: str
    is_current: bool = False

    @classmethod
    def from_domain(
        cls,
        session: IdentitySession,
        *,
        current_session_id: uuid.UUID | str | None = None,
    ) -> "ActiveSessionDTO":
        session_id = str(session.id.value)
        return cls(
            session_id=session_id,
            token_family=session.token_family.id,
            is_current=current_session_id is not None and session_id == str(current_session_id),
        )


class ListActiveSessionsUseCase:
    def __init__(self, *, session_repository: SessionRepository) -> None:
        self.session_repository = session_repository

    def execute(
        self,
        *,
        user_id: uuid.UUID | str,
        current_session_id: uuid.UUID | str | None = None,
    ) -> tuple[ActiveSessionDTO, ...]:
        sessions = self.session_repository.list_active_identity_sessions(user_id=user_id)
        return tuple(
            ActiveSessionDTO.from_domain(session, current_session_id=current_session_id)
            for session in sessions
        )


__all__ = ["ActiveSessionDTO", "ListActiveSessionsUseCase"]
