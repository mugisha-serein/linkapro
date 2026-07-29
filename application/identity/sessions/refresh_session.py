"""Refresh an identity session by rotating a refresh token."""

from typing import Tuple

from application.identity.shared.dtos.token_claims import (
    RotatedTokenPairRequest,
    TokenBootstrapClaims,
)
from application.identity.shared.ports import (
    IdentityTokenService,
    SessionBootstrapReader,
    SessionRepository,
    SessionSecurityStateReader,
    TokenRevocationStore,
)
from domain.identity.authentication import AuthenticationNotAllowed
from domain.identity.sessions import SessionPolicy

from .apply_refresh_rotation import apply_refresh_decision, raise_refresh_rejection


class RefreshSessionUseCase:
    def __init__(
        self,
        *,
        blacklist: TokenRevocationStore,
        session_repository: SessionRepository,
        session_security_state_reader: SessionSecurityStateReader,
        session_bootstrap_reader: SessionBootstrapReader,
        token_service: IdentityTokenService,
        session_policy: SessionPolicy | None = None,
    ) -> None:
        self.blacklist = blacklist
        self.session_repository = session_repository
        self.session_security_state_reader = session_security_state_reader
        self.session_bootstrap_reader = session_bootstrap_reader
        self.token_service = token_service
        self.session_policy = session_policy or SessionPolicy()

    def execute(self, refresh_token: str) -> Tuple[str, str, dict]:
        claims = self.token_service.inspect_refresh_token(
            refresh_token,
            context="refresh_token_rotation",
        )
        decision = self.session_policy.evaluate_refresh_rotation(
            claims,
            token_already_used=self.blacklist.is_blacklisted(claims.jti),
            family_revoked=self.blacklist.is_family_blacklisted(claims.family.id),
            user_sessions_revoked=self.session_security_state_reader.is_token_revoked_for_user(
                claims.user_id,
                claims.issued_at,
            ),
            token_version_matches_active_user=self.session_security_state_reader.token_version_matches_active_user(
                claims.user_id,
                claims.auth_token_version,
            ),
        )
        apply_refresh_decision(
            decision,
            claims,
            claims,
            blacklist=self.blacklist,
            session_repository=self.session_repository,
        )
        if not decision.allowed:
            raise_refresh_rejection(decision)

        bootstrap_claims = self.session_bootstrap_reader.get_bootstrap_claims(claims.user_id, claims.session_id)
        if not bootstrap_claims:
            raise AuthenticationNotAllowed("User is no longer active")

        token_ids = claims.family.rotate()
        issued = self.token_service.issue_rotated_pair(
            RotatedTokenPairRequest(
                claims=claims,
                access_jti=token_ids.access_jti,
                refresh_jti=token_ids.refresh_jti,
                bootstrap_claims=TokenBootstrapClaims(bootstrap_claims),
            )
        )
        return issued.access_token, issued.refresh_token, issued.bootstrap_claims.values

__all__ = ["RefreshSessionUseCase"]
