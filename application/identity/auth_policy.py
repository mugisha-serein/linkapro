from dataclasses import dataclass
from enum import Enum
from typing import Optional

from application.identity.dtos import SessionBootstrapDTO


class AuthenticationStatus(str, Enum):
    AUTHENTICATED = "authenticated"
    MFA_REQUIRED = "mfa_required"
    INVALID_CREDENTIALS = "invalid_credentials"
    INACTIVE = "inactive"
    SOCIAL_LOGIN_ONLY = "social_login_only"
    INVALID_TEMP_TOKEN = "invalid_temp_token"
    INVALID_MFA_CODE = "invalid_mfa_code"


@dataclass(frozen=True)
class AuthenticationDecision:
    status: AuthenticationStatus
    user: Optional[object] = None
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    temp_token: Optional[str] = None
    bootstrap_user: Optional[dict] = None


class IdentityAuthenticationPolicy:
    def __init__(self, token_service):
        self.token_service = token_service

    def evaluate_password_login(self, user, plain_password, password_hasher) -> AuthenticationDecision:
        if not user:
            return AuthenticationDecision(AuthenticationStatus.INVALID_CREDENTIALS)
        if not user.is_active:
            return AuthenticationDecision(AuthenticationStatus.INACTIVE, user=user)
        if not user.password_hash:
            return AuthenticationDecision(AuthenticationStatus.SOCIAL_LOGIN_ONLY, user=user)
        if not password_hasher.verify(plain_password, user.password_hash):
            return AuthenticationDecision(AuthenticationStatus.INVALID_CREDENTIALS, user=user)
        return self._finalize_login(user)

    def evaluate_oauth_login(self, user) -> AuthenticationDecision:
        if not user.is_active:
            return AuthenticationDecision(AuthenticationStatus.INACTIVE, user=user)
        return self._finalize_login(user)

    def evaluate_two_factor_login(self, user, temp_token: str, token: str, totp_secret: Optional[str]) -> AuthenticationDecision:
        if not user:
            return AuthenticationDecision(AuthenticationStatus.INVALID_TEMP_TOKEN)
        if not user.is_active:
            return AuthenticationDecision(AuthenticationStatus.INACTIVE, user=user)
        if not temp_token or not token:
            return AuthenticationDecision(AuthenticationStatus.INVALID_TEMP_TOKEN)
        if not totp_secret:
            return AuthenticationDecision(AuthenticationStatus.INVALID_TEMP_TOKEN, user=user)
        return self.issue_authenticated_login(user)

    def issue_authenticated_login(self, user) -> AuthenticationDecision:
        return self._issue_authenticated_tokens(user)

    def _finalize_login(self, user) -> AuthenticationDecision:
        if user.two_factor_enabled:
            temp_token = self.token_service.create_temp_token(str(user.id))
            return AuthenticationDecision(
                status=AuthenticationStatus.MFA_REQUIRED,
                user=user,
                temp_token=temp_token,
            )
        return self._issue_authenticated_tokens(user)

    def _issue_authenticated_tokens(self, user) -> AuthenticationDecision:
        bootstrap_user = SessionBootstrapDTO.from_user(user).to_dict()
        access_token, refresh_token = self.token_service.create_session_tokens(
            str(user.id), user.role.value, bootstrap_claims=bootstrap_user
        )
        return AuthenticationDecision(
            status=AuthenticationStatus.AUTHENTICATED,
            user=user,
            access_token=access_token,
            refresh_token=refresh_token,
            bootstrap_user=bootstrap_user,
        )
