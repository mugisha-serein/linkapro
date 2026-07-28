"""List active identity sessions for an account."""

import uuid

from application.identity.shared.ports import ISessionStore
from domain.identity.sessions import IdentitySession


class ListActiveSessionsUseCase:
    def __init__(self, *, session_repository: ISessionStore) -> None:
        self.session_repository = session_repository

    def execute(self, *, user_id: uuid.UUID | str) -> tuple[IdentitySession, ...]:
        return self.session_repository.list_active_identity_sessions(user_id=user_id)


__all__ = ["ListActiveSessionsUseCase"]
