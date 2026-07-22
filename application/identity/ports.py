from typing import Protocol


SESSION_ID_CLAIM = "session_id"


class ISessionStore(Protocol):
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


class ITokenBlacklist(Protocol):
    def is_blacklisted(self, jti: str) -> bool:
        ...

    def blacklist(self, jti: str, ttl: int) -> None:
        ...

    def is_family_blacklisted(self, family_id: str) -> bool:
        ...

    def blacklist_family(self, family_id: str) -> None:
        ...
