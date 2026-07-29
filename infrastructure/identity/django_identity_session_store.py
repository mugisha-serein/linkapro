from application.identity.shared.mappers import session_bootstrap_payload_from_values
from application.identity.shared.ports import SessionBootstrapReader, SessionRepository, SessionSecurityStateReader
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
from domain.identity.sessions import IdentitySession, SessionId, SessionStatus, TokenFamily


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
        from django_app.identity.models import User

        user = User.objects.filter(id=user_id, is_active=True).first()
        if not user:
            return None

        return session_bootstrap_payload_from_values(
            id=user.id,
            email=user.email,
            role=user.role,
            first_name=user.first_name,
            last_name=user.last_name,
            is_active=user.is_active,
            is_verified=user.is_verified,
            has_password=bool(user.password),
            two_factor_enabled=user.two_factor_enabled,
            auth_token_version=user.auth_token_version,
            created_at=user.created_at,
            last_login=user.last_login,
            session_id=session_id,
        )

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
        from django.utils import timezone
        from django_app.identity.models import IdentitySession as DjangoIdentitySession

        return DjangoIdentitySession.objects.filter(
            user_id=user_id,
            revoked_at__isnull=True,
        ).update(
            revoked_at=timezone.now(),
            revoked_reason=reason[:255],
        )

    def list_active_identity_sessions(self, *, user_id) -> tuple[IdentitySession, ...]:
        from django_app.identity.models import IdentitySession as DjangoIdentitySession

        sessions = DjangoIdentitySession.objects.filter(
            user_id=user_id,
            revoked_at__isnull=True,
        ).order_by("-last_seen_at", "-created_at")
        return tuple(self._to_domain_session(session) for session in sessions)

    @staticmethod
    def _to_domain_session(session) -> IdentitySession:
        status = SessionStatus.REVOKED if session.revoked_at else SessionStatus.ACTIVE
        return IdentitySession(
            id=SessionId(str(session.id)),
            user_id=session.user_id,
            token_family=TokenFamily(session.token_family, revoked=bool(session.revoked_at)),
            status=status,
            revoked_at=session.revoked_at,
            revoked_reason=session.revoked_reason or None,
        )
