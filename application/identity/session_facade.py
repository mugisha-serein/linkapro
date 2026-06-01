from dataclasses import dataclass
from typing import Optional

from application.identity.auth_policy import AuthenticationDecision
from application.identity.commands import LoginTwoFactorCommand, LoginUserCommand


@dataclass(frozen=True)
class SessionRefreshResult:
    access_token: str
    refresh_token: str
    bootstrap_user: dict


class IdentitySessionFacade:
    def __init__(self, command_handlers, google_login_use_case, token_handlers):
        self.command_handlers = command_handlers
        self.google_login_use_case = google_login_use_case
        self.token_handlers = token_handlers

    def login(self, cmd: LoginUserCommand) -> AuthenticationDecision:
        return self.command_handlers.login_user(cmd)

    def login_two_factor(self, cmd: LoginTwoFactorCommand) -> AuthenticationDecision:
        return self.command_handlers.login_two_factor(cmd)

    def oauth_login(
        self,
        user_data: dict,
        token_data: Optional[dict] = None,
        signup_role: Optional[str] = None,
    ):
        return self.google_login_use_case.execute(user_data, token_data, signup_role=signup_role)

    def refresh_session(self, refresh_token: str) -> SessionRefreshResult:
        access_token, new_refresh_token, bootstrap_user = self.token_handlers.refresh_access_token(refresh_token)
        return SessionRefreshResult(
            access_token=access_token,
            refresh_token=new_refresh_token,
            bootstrap_user=bootstrap_user,
        )

    def revoke_session(self, refresh_token: str) -> None:
        self.token_handlers.revoke_refresh_token(refresh_token)
