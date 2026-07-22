from application.identity.ports import ISessionStore
from django_app.identity.session_tracking import (
    create_identity_session,
    identity_session_is_active,
    revoke_identity_session,
    touch_identity_session,
)


class DjangoIdentitySessionStore(ISessionStore):
    def create_identity_session(
        self,
        *,
        user_id: str,
        token_family: str,
        device_label: str | None = None,
        user_agent_hash: str | None = None,
        ip_hash: str | None = None,
    ) -> str:
        return create_identity_session(
            user_id=user_id,
            token_family=token_family,
            device_label=device_label,
            user_agent_hash=user_agent_hash,
            ip_hash=ip_hash,
        )

    def touch_identity_session(self, session_id: str | None, token_family: str | None = None) -> None:
        touch_identity_session(session_id, token_family)

    def identity_session_is_active(self, session_id: str | None, token_family: str | None = None) -> bool:
        return identity_session_is_active(session_id, token_family)

    def revoke_identity_session(
        self,
        *,
        session_id: str | None = None,
        token_family: str | None = None,
        reason: str = "session_revoked",
    ) -> None:
        revoke_identity_session(
            session_id=session_id,
            token_family=token_family,
            reason=reason,
        )
