# No Business Logic Here
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apps.accounts.application.dto.auth_dto import (
    LoginCommand,
    LoginResult,
    LogoutCommand,
    LogoutResult,
    RefreshTokenCommand,
    RefreshTokenResult,
    RegisterUserCommand,
    RegisterUserResult,
    RevokeSessionCommand,
    RevokeSessionResult,
)
from apps.accounts.application.dto.security_dto import (
    EvaluateLoginSecurityCommand,
    EvaluateLoginSecurityResult,
)
from apps.accounts.application.ports.repositories import (
    DeviceRepository,
    LoginActivityRepository,
    SessionRepository,
    TokenRepository,
    UserRepository,
)
from apps.accounts.application.ports.services import CredentialVerifier, TokenIssuer
from apps.accounts.application.use_cases.auth.login import LoginUseCase
from apps.accounts.application.use_cases.auth.logout import LogoutUseCase
from apps.accounts.application.use_cases.auth.refresh_token import RefreshTokenUseCase
from apps.accounts.application.use_cases.auth.register_user import RegisterUserUseCase
from apps.accounts.application.use_cases.auth.revoke_session import RevokeSessionUseCase
from apps.accounts.application.use_cases.security.evaluate_login_security import EvaluateLoginSecurityUseCase


@dataclass(slots=True)
class AuthOrchestrator:
    """
    High-level orchestrator for authentication operations.

    Coordinates multiple use cases to provide comprehensive auth workflows.
    """

    # Repositories
    user_repository: UserRepository
    device_repository: DeviceRepository
    session_repository: SessionRepository
    token_repository: TokenRepository
    login_activity_repository: LoginActivityRepository

    # Services
    credential_verifier: CredentialVerifier
    token_issuer: TokenIssuer

    # Use Cases
    login_use_case: LoginUseCase | None = None
    logout_use_case: LogoutUseCase | None = None
    refresh_token_use_case: RefreshTokenUseCase | None = None
    register_user_use_case: RegisterUserUseCase | None = None
    revoke_session_use_case: RevokeSessionUseCase | None = None
    evaluate_security_use_case: EvaluateLoginSecurityUseCase | None = None

    def __post_init__(self):
        """Initialize use cases if not provided."""
        if self.login_use_case is None:
            self.login_use_case = LoginUseCase(
                user_repository=self.user_repository,
                device_repository=self.device_repository,
                session_repository=self.session_repository,
                token_repository=self.token_repository,
                login_activity_repository=self.login_activity_repository,
                credential_verifier=self.credential_verifier,
                token_issuer=self.token_issuer,
            )

        if self.logout_use_case is None:
            self.logout_use_case = LogoutUseCase(
                session_repository=self.session_repository,
                token_repository=self.token_repository,
                login_activity_repository=self.login_activity_repository,
            )

        if self.refresh_token_use_case is None:
            self.refresh_token_use_case = RefreshTokenUseCase(
                session_repository=self.session_repository,
                token_repository=self.token_repository,
                login_activity_repository=self.login_activity_repository,
                token_issuer=self.token_issuer,
            )

        if self.register_user_use_case is None:
            self.register_user_use_case = RegisterUserUseCase(
                user_repository=self.user_repository,
                login_activity_repository=self.login_activity_repository,
            )

        if self.revoke_session_use_case is None:
            self.revoke_session_use_case = RevokeSessionUseCase(
                session_repository=self.session_repository,
                token_repository=self.token_repository,
                login_activity_repository=self.login_activity_repository,
            )

        if self.evaluate_security_use_case is None:
            self.evaluate_security_use_case = EvaluateLoginSecurityUseCase(
                user_repository=self.user_repository,
                device_repository=self.device_repository,
                session_repository=self.session_repository,
                login_activity_repository=self.login_activity_repository,
            )

    # Authentication workflow methods
    def authenticate_user(self, command: LoginCommand) -> LoginResult:
        """Complete authentication workflow with security evaluation."""
        if not self.login_use_case:
            return LoginResult(
                authenticated=False,
                status="ERROR",
                failure_reason="LOGIN_USE_CASE_NOT_CONFIGURED",
            )

        # First, evaluate security
        security_command = EvaluateLoginSecurityCommand(
            user_id="",  # We'll get this from email lookup
            ip_address=command.ip_address,
            user_agent=command.user_agent,
            fingerprint_hash=command.fingerprint_hash,
            country_code=command.country_code,
            device_type=command.device_type,
            browser=command.browser,
            os=command.os,
            timezone=command.timezone,
            language=command.language,
        )

        # For security evaluation, we need to find the user first
        from apps.accounts.infrastructure.db.models import User
        normalized_email = command.email.strip().lower()
        user = self.user_repository.get_by_email(normalized_email)

        if user:
            security_command = EvaluateLoginSecurityCommand(
                user_id=str(user.id),
                ip_address=command.ip_address,
                user_agent=command.user_agent,
                fingerprint_hash=command.fingerprint_hash,
                country_code=command.country_code,
                device_type=command.device_type,
                browser=command.browser,
                os=command.os,
                timezone=command.timezone,
                language=command.language,
            )

            security_result = self.evaluate_security_use_case(security_command)

            # If security evaluation blocks login, return blocked result
            if not security_result.allow_login:
                return LoginResult(
                    authenticated=False,
                    status="BLOCKED",
                    failure_reason=f"SECURITY_BLOCKED: {', '.join(security_result.flags)}",
                )

        # Proceed with login
        return self.login_use_case(command)

    def register_and_authenticate(self, command: RegisterUserCommand) -> RegisterUserResult:
        """Register a new user."""
        if not self.register_user_use_case:
            return RegisterUserResult(
                success=False,
                status="ERROR",
                failure_reason="REGISTER_USE_CASE_NOT_CONFIGURED",
            )

        return self.register_user_use_case(command)

    def logout_user(self, command: LogoutCommand) -> LogoutResult:
        """Logout user from session."""
        if not self.logout_use_case:
            return LogoutResult(
                success=False,
                status="ERROR",
                failure_reason="LOGOUT_USE_CASE_NOT_CONFIGURED",
            )

        return self.logout_use_case(command)

    def refresh_user_token(self, command: RefreshTokenCommand) -> RefreshTokenResult:
        """Refresh user authentication tokens."""
        if not self.refresh_token_use_case:
            return RefreshTokenResult(
                success=False,
                status="ERROR",
                failure_reason="REFRESH_TOKEN_USE_CASE_NOT_CONFIGURED",
            )

        return self.refresh_token_use_case(command)

    def revoke_user_session(self, command: RevokeSessionCommand) -> RevokeSessionResult:
        """Revoke a specific user session."""
        if not self.revoke_session_use_case:
            return RevokeSessionResult(
                success=False,
                status="ERROR",
                failure_reason="REVOKE_SESSION_USE_CASE_NOT_CONFIGURED",
            )

        return self.revoke_session_use_case(command)

    def evaluate_login_security(self, command: EvaluateLoginSecurityCommand) -> EvaluateLoginSecurityResult:
        """Evaluate security risk for a login attempt."""
        if not self.evaluate_security_use_case:
            return EvaluateLoginSecurityResult(
                risk_score=100,
                risk_level="CRITICAL",
                flags=["EVALUATION_UNAVAILABLE"],
                recommendations=["Block login"],
                allow_login=False,
            )

        return self.evaluate_security_use_case(command)