from application.identity.ports import AUTH_TOKEN_VERSION_CLAIM, ISessionStore, SESSION_ID_CLAIM
from django_app.identity.session_revocation import (
    is_token_revoked_for_user,
    token_version_matches_active_user,
)
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

    def is_token_revoked_for_user(self, user_id, issued_at) -> bool:
        return is_token_revoked_for_user(user_id, issued_at)

    def token_version_matches_active_user(self, user_id, token_version) -> bool:
        return token_version_matches_active_user(user_id, token_version)

    def get_bootstrap_claims(self, user_id, session_id: str | None = None) -> dict | None:
        from django_app.identity.models import User

        user = User.objects.filter(id=user_id, is_active=True).first()
        if not user:
            return None

        has_password = bool(user.password)
        display_name = f"{user.first_name} {user.last_name}".strip() or user.email
        claims = {
            "id": str(user.id),
            "email": user.email,
            "role": user.role,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "display_name": display_name,
            "avatar": None,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "last_login": user.last_login.isoformat() if user.last_login else None,
            "is_active": user.is_active,
            "is_verified": user.is_verified,
            "has_password": has_password,
            "requires_password_setup": not has_password,
            "two_factor_enabled": user.two_factor_enabled,
            AUTH_TOKEN_VERSION_CLAIM: user.auth_token_version,
            "is_authenticated": True,
            "onboarding_complete": bool(user.is_verified and has_password),
        }
        if session_id:
            claims[SESSION_ID_CLAIM] = str(session_id)
        return claims

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
