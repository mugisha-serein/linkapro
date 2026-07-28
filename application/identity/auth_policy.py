from enum import Enum

from application.identity.dtos import AuthenticationResult
from application.identity.shared.mappers import session_bootstrap_payload
from application.identity.shared.dtos import TokenClaims
from application.identity.shared.ports import ISessionStore, PasswordHasher, SESSION_ID_CLAIM
from domain.identity.authentication import evaluate_authentication_eligibility
from domain.identity.sessions import TokenFamily


class AuthenticationStatus(str, Enum):
    AUTHENTICATED = "authenticated"
    MFA_REQUIRED = "mfa_required"
    INVALID_CREDENTIALS = "invalid_credentials"
    INACTIVE = "inactive"
    SOCIAL_LOGIN_ONLY = "social_login_only"
    INVALID_TEMP_TOKEN = "invalid_temp_token"
    INVALID_MFA_CODE = "invalid_mfa_code"


AuthenticationDecision = AuthenticationResult


class IdentityAuthenticationPolicy:
    def __init__(self, token_service, session_store: ISessionStore):
        self.token_service = token_service
        self.session_store = session_store

    def evaluate_password_login(self, user, plain_password, password_hasher: PasswordHasher) -> AuthenticationDecision:
        eligibility = evaluate_authentication_eligibility(user)
        if not eligibility.allowed:
            return AuthenticationDecision(AuthenticationStatus.INACTIVE, user=user)
        if not user.password_hash:
            return AuthenticationDecision(AuthenticationStatus.SOCIAL_LOGIN_ONLY, user=user)
        if not password_hasher.verify(plain_password, user.password_hash):
            return AuthenticationDecision(AuthenticationStatus.INVALID_CREDENTIALS, user=user)
        return self._finalize_login(user, eligibility)

    def evaluate_oauth_login(self, user) -> AuthenticationDecision:
        eligibility = evaluate_authentication_eligibility(user)
        if not eligibility.allowed:
            return AuthenticationDecision(AuthenticationStatus.INACTIVE, user=user)
        return self._finalize_login(user, eligibility)

    def issue_authenticated_login(self, user) -> AuthenticationDecision:
        return self._issue_authenticated_tokens(user)

    def _finalize_login(self, user, eligibility) -> AuthenticationDecision:
        if eligibility.requires_mfa:
            temp_token = self.token_service.create_temp_token(str(user.id))
            return AuthenticationDecision(
                status=AuthenticationStatus.MFA_REQUIRED,
                user=user,
                temp_token=temp_token,
            )
        return self._issue_authenticated_tokens(user)

    def _issue_authenticated_tokens(self, user) -> AuthenticationDecision:
        token_family = TokenFamily.issue()
        session_id = self.session_store.create_identity_session(user_id=str(user.id), token_family=token_family.id)
        bootstrap_user = session_bootstrap_payload(user, session_id=session_id)
        token_claims = TokenClaims(
            user_id=str(user.id),
            role=user.role.value,
            family=token_family.id,
            session_id=session_id,
            auth_token_version=getattr(user, "auth_token_version", 0),
        )
        access_token = self.token_service.create_access_token(
            token_claims.user_id,
            token_claims.role or "",
            family_id=token_claims.family,
            bootstrap_claims=bootstrap_user,
            auth_token_version=token_claims.auth_token_version,
        )
        refresh_token = self.token_service.create_refresh_token(
            token_claims.user_id,
            token_claims.role,
            family_id=token_claims.family,
            bootstrap_claims=bootstrap_user,
            auth_token_version=token_claims.auth_token_version,
        )
        return AuthenticationDecision(
            status=AuthenticationStatus.AUTHENTICATED,
            user=user,
            access_token=access_token,
            refresh_token=refresh_token,
            bootstrap_user=bootstrap_user,
        )
