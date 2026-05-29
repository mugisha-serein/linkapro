import uuid
import pytest
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
    assert payload["env"] == settings.PAYMENT_ENV

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
    assert decoded["env"] == settings.PAYMENT_ENV


def test_session_tokens_share_family():
    service = JWTTokenService()
    access, refresh = service.create_session_tokens("user-123", "planner")
    access_payload = AccessToken(access)
    refresh_payload = RefreshToken(refresh)

    assert access_payload["family"] == refresh_payload["family"]
    assert access_payload["env"] == settings.PAYMENT_ENV
    assert refresh_payload["env"] == settings.PAYMENT_ENV


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
