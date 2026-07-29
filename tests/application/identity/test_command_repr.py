import uuid
from datetime import UTC, datetime

from application.identity.authentication import AuthenticationDecision, AuthenticationStatus
from application.identity.account.register_account_command import RegisterUserCommand
from application.identity.authentication.complete_mfa_login_command import LoginTwoFactorCommand
from application.identity.authentication.login_with_password_command import LoginUserCommand
from application.identity.mfa.confirm_mfa_enrollment_command import VerifyTwoFactorSetupCommand
from application.identity.oauth.google_login_command import OAuthLoginCommand, ProviderIdentity
from application.identity.recovery.reset_password_command import (
    PasswordResetTokenInput,
    ResetPasswordCommand,
    SecurityMetadataHash,
)
from application.identity.verification.verify_email_command import VerifyEmailCommand
from application.identity.dtos import AuthenticationResultDTO, TwoFactorChallengeDTO, TwoFactorSetupDTO, UserDTO
from application.identity.shared.dtos import IssuedTokenPair, RefreshTokenClaims, TokenBootstrapClaims
from application.identity.oauth import GoogleLoginResult
from domain.identity.account import AccountRole
from domain.identity.credentials import Email, PlainPassword
from domain.identity.oauth import OAuthAccessToken, OAuthProvider, OAuthRefreshToken
from domain.identity.verification import EmailVerificationToken, VerificationCode


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
        VerifyEmailCommand(
            verification_token=EmailVerificationToken("raw-email-verification-token")
        ),
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
            token=PasswordResetTokenInput("raw-reset-token"),
            new_password=PlainPassword("ResetPass1!"),
            client_ip_hash=SecurityMetadataHash("a" * 64),
            user_agent_hash=SecurityMetadataHash("b" * 64),
        ),
        "raw-reset-token",
        "ResetPass1!",
    )


def test_oauth_login_command_redacts_provider_tokens():
    _assert_repr_hides(
        OAuthLoginCommand(
            identity=ProviderIdentity(
                provider=OAuthProvider.GOOGLE,
                provider_user_id="google-user-id",
                email=Email("oauth@example.com"),
                first_name="OAuth",
                last_name="User",
                email_verified=True,
            ),
            access_token=OAuthAccessToken("raw-oauth-access-token"),
            refresh_token=OAuthRefreshToken("raw-oauth-refresh-token"),
            expires_at=datetime(2026, 1, 1, tzinfo=UTC),
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
