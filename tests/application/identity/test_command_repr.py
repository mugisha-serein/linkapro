import uuid
from datetime import UTC, datetime

from application.identity.auth_policy import AuthenticationDecision, AuthenticationStatus
from application.identity.commands import (
    LoginTwoFactorCommand,
    LoginUserCommand,
    OAuthLoginCommand,
    RegisterUserCommand,
    ResetPasswordCommand,
    VerifyEmailCommand,
    VerifyTwoFactorSetupCommand,
)
from application.identity.dtos import AuthenticationResultDTO, TwoFactorChallengeDTO, TwoFactorSetupDTO, UserDTO
from application.identity.shared.dtos import IssuedTokenPair, RefreshTokenClaims, TokenBootstrapClaims
from application.identity.session_facade import SessionRefreshResult
from application.identity.use_cases.google_login import GoogleLoginResult
from domain.identity.account import AccountRole
from domain.identity.credentials import Email, PlainPassword
from domain.identity.oauth import OAuthAccessToken, OAuthProvider, OAuthRefreshToken
from domain.identity.verification import VerificationCode


def _assert_repr_hides(command, *secrets: str) -> None:
    rendered = repr(command)
    for secret in secrets:
        assert secret not in rendered


def test_secret_bearing_identity_commands_do_not_expose_raw_values_in_repr():
    _assert_repr_hides(
        RegisterUserCommand(
            email=Email("register@example.com"),
            plain_password=PlainPassword("RegisterPass1!"),
            first_name="Reg",
            last_name="User",
            role=AccountRole.PLANNER,
        ),
        "RegisterPass1!",
    )
    _assert_repr_hides(
        LoginUserCommand(
            email=Email("login@example.com"),
            plain_password=PlainPassword("LoginPass1!"),
        ),
        "LoginPass1!",
    )
    _assert_repr_hides(
        VerifyEmailCommand(verification_token="raw-email-verification-token"),
        "raw-email-verification-token",
    )
    _assert_repr_hides(
        VerifyTwoFactorSetupCommand(user_id=uuid.uuid4(), token=VerificationCode("123456")),
        "123456",
    )
    _assert_repr_hides(
        LoginTwoFactorCommand(temp_token="raw-temp-token", token=VerificationCode("654321")),
        "raw-temp-token",
        "654321",
    )
    _assert_repr_hides(
        ResetPasswordCommand(
            token="raw-reset-token",
            new_password="ResetPass1!",
            client_ip="127.0.0.1",
            user_agent="test",
        ),
        "raw-reset-token",
        "ResetPass1!",
    )


def test_oauth_login_command_redacts_provider_tokens():
    _assert_repr_hides(
        OAuthLoginCommand(
            provider=OAuthProvider.GOOGLE,
            provider_user_id="google-user-id",
            access_token=OAuthAccessToken("raw-oauth-access-token"),
            refresh_token=OAuthRefreshToken("raw-oauth-refresh-token"),
            signup_role=AccountRole.PLANNER,
        ),
        "raw-oauth-access-token",
        "raw-oauth-refresh-token",
    )


def test_secret_bearing_identity_result_dtos_do_not_expose_raw_values_in_repr():
    dummy_user = UserDTO(
        id=uuid.uuid4(),
        email="user@example.com",
        first_name="Test",
        last_name="User",
        role="planner",
        is_active=True,
        is_verified=True,
        created_at=datetime.now(UTC),
        last_login=None,
    )

    _assert_repr_hides(
        TwoFactorSetupDTO(
            enrollment_id="enrollment-id",
            secret="raw-totp-setup-secret",
            provisioning_uri="otpauth://totp/linkapro",
        ),
        "raw-totp-setup-secret",
    )
    _assert_repr_hides(
        TwoFactorChallengeDTO(temp_token="raw-temp-token", expires_in=180),
        "raw-temp-token",
    )
    _assert_repr_hides(
        AuthenticationDecision(
            status=AuthenticationStatus.AUTHENTICATED,
            access_token="raw-access-token",
            refresh_token="raw-refresh-token",
            temp_token="raw-temp-token",
        ),
        "raw-access-token",
        "raw-refresh-token",
        "raw-temp-token",
    )
    _assert_repr_hides(
        AuthenticationResultDTO(
            user=dummy_user,
            access_token="raw-auth-result-access",
            refresh_token="raw-auth-result-refresh",
        ),
        "raw-auth-result-access",
        "raw-auth-result-refresh",
    )
    _assert_repr_hides(
        GoogleLoginResult(
            requires_2fa=False,
            temp_token="raw-google-temp-token",
            access="raw-google-access-token",
            refresh="raw-google-refresh-token",
        ),
        "raw-google-temp-token",
        "raw-google-access-token",
        "raw-google-refresh-token",
    )
    _assert_repr_hides(
        SessionRefreshResult(
            access_token="raw-session-access-token",
            refresh_token="raw-session-refresh-token",
            bootstrap_user={"id": "user-id"},
        ),
        "raw-session-access-token",
        "raw-session-refresh-token",
    )
    _assert_repr_hides(
        IssuedTokenPair(
            access_token="raw-issued-access-token",
            refresh_token="raw-issued-refresh-token",
            bootstrap_claims=TokenBootstrapClaims(values={"id": "user-id"}),
        ),
        "raw-issued-access-token",
        "raw-issued-refresh-token",
    )
    _assert_repr_hides(
        RefreshTokenClaims(
            raw="raw-parsed-refresh-token",
            jti="refresh-jti",
            family="family-id",
            user_id="user-id",
            session_id="session-id",
            issued_at=1,
            expires_at=2,
            auth_token_version=3,
        ),
        "raw-parsed-refresh-token",
    )
