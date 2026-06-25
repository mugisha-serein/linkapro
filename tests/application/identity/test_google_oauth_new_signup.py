import pytest

from application.identity.use_cases.google_login import GoogleLoginUseCase
from infrastructure.adapters.jwt_token_service import JWTTokenService
from infrastructure.repos.django_oauth_token_repository import DjangoOAuthTokenRepository
from infrastructure.repos.django_user_repository import DjangoUserRepository
from django_app.identity.models import User as DjangoUser


pytestmark = pytest.mark.django_db(transaction=True)


class _Dispatcher:
    def __init__(self):
        self.events = []

    def dispatch(self, event):
        self.events.append(event)


def test_new_google_email_creates_user_and_returns_session_tokens():
    dispatcher = _Dispatcher()
    use_case = GoogleLoginUseCase(
        user_repo=DjangoUserRepository(),
        oauth_repo=DjangoOAuthTokenRepository(),
        token_service=JWTTokenService(),
        event_dispatcher=dispatcher,
    )

    result = use_case.execute(
        user_data={
            "google_id": "google-new-123",
            "email": "google-new@example.com",
            "name": "Google New",
        },
        token_data={
            "access_token": "google-access-token",
            "refresh_token": "google-refresh-token",
            "expires_in": 3600,
        },
        signup_role="planner",
    )

    created_user = DjangoUser.objects.get(email="google-new@example.com")

    assert result.requires_2fa is False
    assert result.access
    assert result.refresh
    assert result.bootstrap_user["email"] == "google-new@example.com"
    assert created_user.role == "planner"
    assert created_user.is_verified is True
