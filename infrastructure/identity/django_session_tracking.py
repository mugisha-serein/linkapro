"""Django-backed identity session record helpers."""

from __future__ import annotations

from django.db import IntegrityError
from django.utils import timezone

from application.identity.shared.ports import SESSION_ID_CLAIM
from application.identity.shared.mappers import session_bootstrap_payload_from_values
from infrastructure.identity.django_models import identity_session_model, user_model
from domain.identity.sessions import IdentitySession as DomainIdentitySession
from domain.identity.sessions import SessionId, SessionStatus, TokenFamily


DEFAULT_DEVICE_LABEL = "Unknown device"


def create_identity_session(
    *,
    user_id: str,
    token_family: str,
    device_label: str | None = None,
    user_agent_hash: str | None = None,
    ip_hash: str | None = None,
) -> str:
    label = (device_label or DEFAULT_DEVICE_LABEL).strip() or DEFAULT_DEVICE_LABEL
    now = timezone.now()
    IdentitySession = identity_session_model()
    try:
        identity_session = IdentitySession.objects.create(
            user_id=user_id,
            token_family=token_family,
            device_label=label,
            user_agent_hash=user_agent_hash,
            ip_hash=ip_hash,
            created_at=now,
            last_seen_at=now,
        )
    except IntegrityError:
        identity_session = IdentitySession.objects.get(token_family=token_family)
    return str(identity_session.id)


def touch_identity_session(session_id: str | None, token_family: str | None = None) -> None:
    if not session_id:
        return

    filters = {"id": session_id, "revoked_at__isnull": True}
    if token_family:
        filters["token_family"] = token_family
    identity_session_model().objects.filter(**filters).update(last_seen_at=timezone.now())


def identity_session_is_active(session_id: str | None, token_family: str | None = None) -> bool:
    if not session_id:
        return True

    filters = {"id": session_id, "revoked_at__isnull": True}
    if token_family:
        filters["token_family"] = token_family
    return identity_session_model().objects.filter(**filters).exists()


def revoke_identity_session(
    *,
    session_id: str | None = None,
    token_family: str | None = None,
    reason: str = "session_revoked",
) -> None:
    if not session_id and not token_family:
        return

    filters = {"revoked_at__isnull": True}
    if session_id:
        filters["id"] = session_id
    if token_family:
        filters["token_family"] = token_family
    identity_session_model().objects.filter(**filters).update(
        revoked_at=timezone.now(),
        revoked_reason=reason[:255],
    )


def revoke_all_identity_sessions(*, user_id, reason: str = "session_revoked") -> int:
    return identity_session_model().objects.filter(
        user_id=user_id,
        revoked_at__isnull=True,
    ).update(
        revoked_at=timezone.now(),
        revoked_reason=reason[:255],
    )


def list_active_identity_sessions(*, user_id) -> tuple[DomainIdentitySession, ...]:
    sessions = identity_session_model().objects.filter(
        user_id=user_id,
        revoked_at__isnull=True,
    ).order_by("-last_seen_at", "-created_at")
    return tuple(_to_domain_session(session) for session in sessions)


def get_bootstrap_claims(user_id, session_id: str | None = None) -> dict | None:
    user = user_model().objects.filter(id=user_id, is_active=True).first()
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


def _to_domain_session(session) -> DomainIdentitySession:
    status = SessionStatus.REVOKED if session.revoked_at else SessionStatus.ACTIVE
    return DomainIdentitySession(
        id=SessionId(str(session.id)),
        user_id=session.user_id,
        token_family=TokenFamily(session.token_family, revoked=bool(session.revoked_at)),
        status=status,
        revoked_at=session.revoked_at,
        revoked_reason=session.revoked_reason or None,
    )


__all__ = [
    "DEFAULT_DEVICE_LABEL",
    "SESSION_ID_CLAIM",
    "create_identity_session",
    "get_bootstrap_claims",
    "identity_session_is_active",
    "list_active_identity_sessions",
    "revoke_all_identity_sessions",
    "revoke_identity_session",
    "touch_identity_session",
]
