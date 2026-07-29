from application.identity.shared.ports import SessionBootstrapReader, SessionRepository, SessionSecurityStateReader
from infrastructure.identity.django_session_revocation import (
    is_token_revoked_for_user,
    token_version_matches_active_user,
)
from infrastructure.identity.django_session_tracking import (
    create_identity_session,
    get_bootstrap_claims,
    identity_session_is_active,
    list_active_identity_sessions,
    revoke_all_identity_sessions,
    revoke_identity_session,
    touch_identity_session,
)


class DjangoIdentitySessionStore(SessionRepository, SessionSecurityStateReader, SessionBootstrapReader):
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

    def is_token_revoked_for_user(self, user_id, issued_at) -> bool:
        return is_token_revoked_for_user(user_id, issued_at)

    def token_version_matches_active_user(self, user_id, token_version) -> bool:
        return token_version_matches_active_user(user_id, token_version)

    def get_bootstrap_claims(self, user_id, session_id: str | None = None) -> dict | None:
        return get_bootstrap_claims(user_id, session_id=session_id)

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

    def revoke_all_identity_sessions(
        self,
        *,
        user_id,
        reason: str = "session_revoked",
    ) -> int:
        return revoke_all_identity_sessions(user_id=user_id, reason=reason)

    def list_active_identity_sessions(self, *, user_id):
        return list_active_identity_sessions(user_id=user_id)
