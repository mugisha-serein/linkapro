"""Revoke the session represented by a presented refresh token."""

from application.identity.shared.ports import IdentityTokenService, SessionRepository, TokenRevocationStore
from domain.identity.sessions import SessionPolicy

from .apply_refresh_rotation import apply_refresh_decision


class RevokeCurrentSessionUseCase:
    def __init__(
        self,
        *,
        blacklist: TokenRevocationStore,
        session_repository: SessionRepository,
        token_service: IdentityTokenService,
        session_policy: SessionPolicy | None = None,
    ) -> None:
        self.blacklist = blacklist
        self.session_repository = session_repository
        self.token_service = token_service
        self.session_policy = session_policy or SessionPolicy()

    def execute(self, refresh_token: str) -> None:
        claims = self.token_service.inspect_refresh_token(
            refresh_token,
            context="refresh_token_revoke",
        )
        decision = self.session_policy.revoke_family_for_sign_out(claims)
        apply_refresh_decision(
            decision,
            claims,
            claims,
            blacklist=self.blacklist,
            session_repository=self.session_repository,
        )


__all__ = ["RevokeCurrentSessionUseCase"]
