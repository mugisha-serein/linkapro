"""Session persistence port for identity application services."""

from typing import Protocol
import uuid

from domain.identity.sessions import IdentitySession


SESSION_ID_CLAIM = "session_id"
AUTH_TOKEN_VERSION_CLAIM = "auth_token_version"


class SessionRepository(Protocol):
    def create_identity_session(
        self,
        *,
        user_id: str,
        token_family: str,
        device_label: str | None = None,
        user_agent_hash: str | None = None,
        ip_hash: str | None = None,
    ) -> str:
        ...

    def touch_identity_session(self, session_id: str | None, token_family: str | None = None) -> None:
        ...

    def identity_session_is_active(self, session_id: str | None, token_family: str | None = None) -> bool:
        ...

    def revoke_identity_session(
        self,
        *,
        session_id: str | None = None,
        token_family: str | None = None,
        reason: str = "session_revoked",
    ) -> None:
        ...

    def revoke_all_identity_sessions(
        self,
        *,
        user_id: uuid.UUID | str,
        reason: str = "session_revoked",
    ) -> int:
        ...

    def list_active_identity_sessions(self, *, user_id: uuid.UUID | str) -> tuple[IdentitySession, ...]:
        ...


__all__ = [
    "AUTH_TOKEN_VERSION_CLAIM",
    "SessionRepository",
    "SESSION_ID_CLAIM",
]
