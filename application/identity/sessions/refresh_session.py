"""Refresh an identity session by rotating a refresh token."""

from datetime import datetime, timezone
from typing import Tuple

from application.identity.shared.dtos.token_claims import (
    RefreshTokenClaims,
    RotatedTokenPairRequest,
    TokenBootstrapClaims,
)
from application.identity.shared.ports import IdentityTokenService, ISessionStore, ITokenBlacklist
from domain.identity.authentication import AuthenticationNotAllowed
from domain.identity.sessions import (
    RefreshRotationDecision,
    RefreshTokenSnapshot,
    SessionPolicy,
    SessionRevoked,
    TokenFamily,
)


class RefreshSessionUseCase:
    def __init__(
        self,
        *,
        blacklist: ITokenBlacklist,
        session_store: ISessionStore,
        token_service: IdentityTokenService,
        session_policy: SessionPolicy | None = None,
    ) -> None:
        self.blacklist = blacklist
        self.session_store = session_store
        self.token_service = token_service
        self.session_policy = session_policy or SessionPolicy()

    def execute(self, refresh_token: str) -> Tuple[str, str, dict]:
        claims = self.token_service.inspect_refresh_token(
            refresh_token,
            context="refresh_token_rotation",
        )
        token_snapshot = refresh_snapshot(claims)
        decision = self.session_policy.evaluate_refresh_rotation(
            token_snapshot,
            token_already_used=self.blacklist.is_blacklisted(claims.jti),
            family_revoked=self.blacklist.is_family_blacklisted(claims.family),
            user_sessions_revoked=self.session_store.is_token_revoked_for_user(
                claims.user_id,
                claims.issued_at,
            ),
            token_version_matches_active_user=self.session_store.token_version_matches_active_user(
                claims.user_id,
                claims.auth_token_version,
            ),
        )
        apply_refresh_decision(
            decision,
            token_snapshot,
            claims,
            blacklist=self.blacklist,
            session_store=self.session_store,
        )
        if not decision.allowed:
            raise_refresh_rejection(decision)

        bootstrap_claims = self.session_store.get_bootstrap_claims(claims.user_id, claims.session_id)
        if not bootstrap_claims:
            raise AuthenticationNotAllowed("User is no longer active")

        token_ids = token_snapshot.family.rotate()
        issued = self.token_service.issue_rotated_pair(
            RotatedTokenPairRequest(
                claims=claims,
                access_jti=token_ids.access_jti,
                refresh_jti=token_ids.refresh_jti,
                bootstrap_claims=TokenBootstrapClaims(bootstrap_claims),
            )
        )
        return issued.access_token, issued.refresh_token, issued.bootstrap_claims.values


def remaining_ttl(claims: RefreshTokenClaims) -> int:
    expires_at = datetime.fromtimestamp(int(claims.expires_at), tz=timezone.utc)
    ttl = int((expires_at - datetime.now(timezone.utc)).total_seconds())
    return max(ttl, 1)


def refresh_snapshot(claims: RefreshTokenClaims) -> RefreshTokenSnapshot:
    return RefreshTokenSnapshot(
        jti=claims.jti,
        family=TokenFamily(claims.family),
        session_id=claims.session_id,
        user_id=claims.user_id,
        issued_at=claims.issued_at,
        auth_token_version=claims.auth_token_version,
    )


def apply_refresh_decision(
    decision: RefreshRotationDecision,
    token_snapshot: RefreshTokenSnapshot,
    claims: RefreshTokenClaims,
    *,
    blacklist: ITokenBlacklist,
    session_store: ISessionStore,
) -> None:
    if decision.blacklist_presented_token:
        blacklist.blacklist(token_snapshot.jti, ttl=remaining_ttl(claims))
    if decision.revoke_family:
        blacklist.blacklist_family(token_snapshot.family.id)
    if decision.touch_session:
        session_store.touch_identity_session(token_snapshot.session_id, token_snapshot.family.id)
    if decision.revoke_session and decision.reason is not None:
        session_store.revoke_identity_session(
            session_id=token_snapshot.session_id,
            token_family=token_snapshot.family.id,
            reason=decision.reason.value,
        )


def raise_refresh_rejection(decision: RefreshRotationDecision) -> None:
    if decision.error is not None:
        raise decision.error("Token has been revoked")
    raise SessionRevoked("Token has been revoked")


__all__ = [
    "RefreshSessionUseCase",
    "apply_refresh_decision",
    "raise_refresh_rejection",
    "refresh_snapshot",
    "remaining_ttl",
]
