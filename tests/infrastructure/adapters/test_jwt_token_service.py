import uuid
import pytest
from datetime import timedelta
from django.test import override_settings
from infrastructure.adapters.jwt_token_service import JWTTokenService


@override_settings(PASSWORD_RESET_TIMEOUT=timedelta(hours=1))
def test_password_reset_token_roundtrip():
    service = JWTTokenService()
    user_id = str(uuid.uuid4())
    token = service.create_password_reset_token(user_id)
    assert service.verify_password_reset_token(token) == user_id

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