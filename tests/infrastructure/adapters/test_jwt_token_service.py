import pytest
import uuid
from datetime import timedelta
import jwt
from django.test import override_settings
from django.conf import settings
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken
from infrastructure.adapters.jwt_token_service import JWTTokenService


@override_settings(PASSWORD_RESET_TIMEOUT=timedelta(hours=1))
def test_password_reset_token_roundtrip():
    service = JWTTokenService()
    user_id = str(uuid.uuid4())
    token = service.create_password_reset_token(user_id)
    assert service.verify_password_reset_token(token) == user_id
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    assert payload["env"] == settings.TOKEN_ENV
    assert payload["jti"]

def test_invalid_token_returns_none():
    service = JWTTokenService()
    assert service.verify_password_reset_token("garbage") is None

pytestmark = pytest.mark.django_db

@override_settings(
    SECRET_KEY="*5f*tl1v=p0v=(l9f6e)*c7a-bq6mr=sl-!ub3hn42cq0m3br5",
    SIMPLE_JWT={"SIGNING_KEY": "*5f*tl1v=p0v=(l9f6e)*c7a-bq6mr=sl-!ub3hn42cq0m3br5"}
)

def test_wrong_token_type_returns_none():
    service = JWTTokenService()
    token = service.create_access_token("user-123", "planner")
    assert service.verify_password_reset_token(token) is None


def test_access_token_includes_environment_claim():
    service = JWTTokenService()
    token = service.create_access_token("user-123", "planner")
    decoded = AccessToken(token)
    assert decoded["env"] == settings.TOKEN_ENV


def test_session_tokens_share_family():
    service = JWTTokenService()
    access, refresh = service.create_session_tokens("user-123", "planner")
    access_payload = AccessToken(access)
    refresh_payload = RefreshToken(refresh)

    assert access_payload["family"] == refresh_payload["family"]
    assert access_payload["env"] == settings.TOKEN_ENV
    assert refresh_payload["env"] == settings.TOKEN_ENV


def test_session_tokens_embed_bootstrap_claims():
    service = JWTTokenService()
    access, refresh = service.create_session_tokens(
        "user-123",
        "planner",
        bootstrap_claims={
            "email": "test@example.com",
            "first_name": "Test",
            "last_name": "User",
            "display_name": "Test User",
            "avatar": None,
            "is_active": True,
            "is_verified": True,
            "has_password": True,
            "requires_password_setup": False,
            "two_factor_enabled": False,
            "is_authenticated": True,
            "onboarding_complete": True,
            "created_at": "2026-05-28T00:00:00Z",
            "last_login": None,
        },
    )
    access_payload = AccessToken(access)
    refresh_payload = RefreshToken(refresh)

    assert access_payload["display_name"] == "Test User"
    assert access_payload["requires_password_setup"] is False
    assert refresh_payload["display_name"] == "Test User"


@override_settings(TOKEN_ENV="identity-prod", PAYMENT_ENV="payment-live")
def test_password_reset_token_uses_token_env_not_payment_env():
    service = JWTTokenService()
    token = service.create_password_reset_token("user-123")
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])

    assert payload["env"] == "identity-prod"
    assert payload["env"] != settings.PAYMENT_ENV


@override_settings(TOKEN_ENV="identity-prod", PAYMENT_ENV="payment-live")
def test_payment_env_change_does_not_invalidate_password_reset_token(settings):
    service = JWTTokenService()
    token = service.create_password_reset_token("user-123")

    settings.PAYMENT_ENV = "payment-test"

    assert service.verify_password_reset_token(token) == "user-123"


@override_settings(TOKEN_ENV="identity-prod")
def test_token_env_change_invalidates_password_reset_token(settings):
    service = JWTTokenService()
    token = service.create_password_reset_token("user-123")

    settings.TOKEN_ENV = "identity-staging"

    assert service.verify_password_reset_token(token) is None


@override_settings(TOKEN_ENV="identity-prod", PAYMENT_ENV="payment-live")
def test_email_verification_and_temp_tokens_use_token_env():
    service = JWTTokenService()

    email_token = service.create_email_verification_token("user-123")
    temp_token = service.create_temp_token("user-123")

    email_payload = jwt.decode(email_token, settings.SECRET_KEY, algorithms=["HS256"])
    temp_payload = jwt.decode(temp_token, settings.SECRET_KEY, algorithms=["HS256"])
    assert email_payload["env"] == "identity-prod"
    assert temp_payload["env"] == "identity-prod"
    assert service.verify_email_verification_token(email_token) == "user-123"
    assert service.verify_temp_token(temp_token)["user_id"] == "user-123"


@override_settings(TOKEN_ENV="identity-prod", PAYMENT_ENV="legacy-test", ACCEPT_LEGACY_PAYMENT_ENV_TOKENS=True)
def test_legacy_payment_env_password_reset_token_accepted(caplog):
    now = settings.PASSWORD_RESET_TIMEOUT
    token = jwt.encode(
        {
            "user_id": "user-123",
            "token_type": "password_reset",
            "jti": str(uuid.uuid4()),
            "env": "legacy-test",
            "exp": datetime_utc_plus(now),
            "iat": datetime_utc_plus(timedelta(seconds=0)),
        },
        settings.SECRET_KEY,
        algorithm="HS256",
    )
    caplog.set_level("WARNING", logger="infrastructure.adapters.jwt_token_service")

    assert JWTTokenService().verify_password_reset_token(token) == "user-123"
    assert "legacy_identity_token_env_accepted" in caplog.text


@override_settings(TOKEN_ENV="identity-prod", PAYMENT_ENV="legacy-test", ACCEPT_LEGACY_PAYMENT_ENV_TOKENS=False)
def test_legacy_payment_env_password_reset_token_rejected_when_disabled():
    token = jwt.encode(
        {
            "user_id": "user-123",
            "token_type": "password_reset",
            "jti": str(uuid.uuid4()),
            "env": "legacy-test",
            "exp": datetime_utc_plus(settings.PASSWORD_RESET_TIMEOUT),
            "iat": datetime_utc_plus(timedelta(seconds=0)),
        },
        settings.SECRET_KEY,
        algorithm="HS256",
    )

    assert JWTTokenService().verify_password_reset_token(token) is None


@override_settings(TOKEN_ENV="")
def test_missing_token_env_raises_clear_error(caplog):
    caplog.set_level("ERROR", logger="infrastructure.adapters.jwt_token_service")

    with pytest.raises(ValueError, match="TOKEN_ENV must be configured"):
        JWTTokenService().create_password_reset_token("user-123")

    assert "identity_token_env_missing" in caplog.text


def datetime_utc_plus(delta):
    from datetime import datetime, timezone

    return datetime.now(timezone.utc) + delta
