from typing import Tuple

from application.identity.sessions import IssueStepUpTokenUseCase, RefreshSessionUseCase, RevokeSessionUseCase
from application.identity.shared.ports import IdentityTokenService, ISessionStore, ITokenBlacklist
from domain.identity.sessions import SessionPolicy


class TokenCommandHandlers:
    def __init__(
        self,
        blacklist: ITokenBlacklist,
        session_store: ISessionStore,
        token_service: IdentityTokenService,
        session_policy: SessionPolicy | None = None,
    ):
        self.blacklist = blacklist
        self.session_store = session_store
        self.token_service = token_service
        self.session_policy = session_policy or SessionPolicy()
        self.refresh_session_use_case = RefreshSessionUseCase(
            blacklist=blacklist,
            session_store=session_store,
            token_service=token_service,
            session_policy=self.session_policy,
        )
        self.revoke_session_use_case = RevokeSessionUseCase(
            blacklist=blacklist,
            session_store=session_store,
            token_service=token_service,
            session_policy=self.session_policy,
        )
        self.issue_step_up_token_use_case = IssueStepUpTokenUseCase(
            token_service=token_service,
        )

    def refresh_access_token(self, refresh_token: str) -> Tuple[str, str, dict]:
        """Validate refresh token, rotate, and return new access + refresh pair."""
        return self.refresh_session_use_case.execute(refresh_token)

    def revoke_refresh_token(self, refresh_token: str) -> None:
        self.revoke_session_use_case.execute(refresh_token)

    def issue_step_up_token(self, user_id: str, original_token: str) -> str:
        """Issue a short-lived (5 min) access token with step_up=True."""
        return self.issue_step_up_token_use_case.execute(
            user_id=user_id,
            original_token=original_token,
        )
