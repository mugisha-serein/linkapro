"""Revoke an identity refresh-token family."""

from application.identity.shared.ports import IdentityTokenService, ISessionStore, ITokenBlacklist
from domain.identity.sessions import SessionPolicy

from .refresh_session import apply_refresh_decision, refresh_snapshot


class RevokeSessionUseCase:
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

    def execute(self, refresh_token: str) -> None:
        claims = self.token_service.inspect_refresh_token(
            refresh_token,
            context="refresh_token_revoke",
        )
        token_snapshot = refresh_snapshot(claims)
        decision = self.session_policy.revoke_family_for_sign_out(token_snapshot)
        apply_refresh_decision(
            decision,
            token_snapshot,
            claims,
            blacklist=self.blacklist,
            session_store=self.session_store,
        )


__all__ = ["RevokeSessionUseCase"]
