"""Apply domain refresh-rotation decisions to persistence ports."""

from datetime import datetime, timezone

from application.identity.shared.dtos.token_claims import RefreshTokenClaims
from application.identity.shared.ports import SessionRepository, TokenRevocationStore
from domain.identity.sessions import RefreshRotationDecision, RefreshTokenSnapshot, SessionRevoked


def remaining_ttl(claims: RefreshTokenClaims) -> int:
    expires_at = datetime.fromtimestamp(int(claims.expires_at), tz=timezone.utc)
    ttl = int((expires_at - datetime.now(timezone.utc)).total_seconds())
    return max(ttl, 1)


def apply_refresh_decision(
    decision: RefreshRotationDecision,
    token_snapshot: RefreshTokenSnapshot,
    claims: RefreshTokenClaims,
    *,
    blacklist: TokenRevocationStore,
    session_repository: SessionRepository,
) -> None:
    if decision.blacklist_presented_token:
        blacklist.blacklist(token_snapshot.jti, ttl=remaining_ttl(claims))
    if decision.revoke_family:
        blacklist.blacklist_family(token_snapshot.family.id)
    if decision.touch_session:
        session_repository.touch_identity_session(token_snapshot.session_id, token_snapshot.family.id)
    if decision.revoke_session and decision.reason is not None:
        session_repository.revoke_identity_session(
            session_id=token_snapshot.session_id,
            token_family=token_snapshot.family.id,
            reason=decision.reason.value,
        )


def raise_refresh_rejection(decision: RefreshRotationDecision) -> None:
    if decision.error is not None:
        raise decision.error("Token has been revoked")
    raise SessionRevoked("Token has been revoked")


__all__ = ["apply_refresh_decision", "raise_refresh_rejection", "remaining_ttl"]
