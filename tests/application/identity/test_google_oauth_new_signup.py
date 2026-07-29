import pytest
import uuid
from datetime import timedelta
from django.utils import timezone

from application.identity.oauth import GoogleLoginCommand, GoogleLoginUseCase, ProviderIdentity
from application.identity.shared.ports import NullIdentityUnitOfWork
from domain.identity.account import AccountRole
from domain.identity.credentials import Email
from domain.identity.oauth import OAuthAccessToken, OAuthProvider, OAuthRefreshToken
from infrastructure.identity.django_identity_session_store import DjangoIdentitySessionStore
from infrastructure.identity.jwt_token_service import JWTTokenService
from infrastructure.identity.django_oauth_token_repository import DjangoOAuthTokenRepository
from infrastructure.identity.django_user_repository import DjangoUserRepository
from interface.identity.models import OAuthToken as DjangoOAuthToken, User as DjangoUser


pytestmark = pytest.mark.django_db(transaction=True)


class _KeyProvider:
    def wrap_dek(self, dek: bytes) -> bytes:
        return dek

    def unwrap_dek(self, encrypted_dek: bytes) -> bytes:
        return encrypted_dek


class _Dispatcher:
    def __init__(self):
        self.events = []

    def dispatch(self, event):
        self.events.append(event)


class _Clock:
    def now(self):
        return timezone.now()


class _IdGenerator:
    def __init__(self):
        self._next = 1

    def new_id(self):
        value = uuid.UUID(int=self._next)
        self._next += 1
        return value


def test_new_google_email_creates_user_and_returns_session_tokens():
    dispatcher = _Dispatcher()
    use_case = GoogleLoginUseCase(
        user_repo=DjangoUserRepository(),
        oauth_repo=DjangoOAuthTokenRepository(key_provider=_KeyProvider()),
        token_service=JWTTokenService(),
        session_store=DjangoIdentitySessionStore(),
        clock=_Clock(),
        id_generator=_IdGenerator(),
        unit_of_work=NullIdentityUnitOfWork(),
        event_dispatcher=dispatcher,
    )

    result = use_case.execute(
        GoogleLoginCommand(
            identity=ProviderIdentity(
                provider=OAuthProvider.GOOGLE,
                provider_user_id="google-new-123",
                email=Email("google-new@example.com"),
                first_name="Google",
                last_name="New",
                email_verified=True,
            ),
            access_token=OAuthAccessToken("google-access-token"),
            refresh_token=OAuthRefreshToken("google-refresh-token"),
            expires_at=timezone.now() + timedelta(seconds=3600),
            signup_role=AccountRole.PLANNER,
        )
    )

    created_user = DjangoUser.objects.get(email="google-new@example.com")
    saved_oauth_token = DjangoOAuthToken.objects.get(user=created_user, provider="google")

    assert result.requires_2fa is False
    assert result.access
    assert result.refresh
    assert result.bootstrap_user["email"] == "google-new@example.com"
    assert created_user.role == "planner"
    assert created_user.is_verified is True
    assert saved_oauth_token.encrypted_access_token["ciphertext"] != "google-access-token"
    assert saved_oauth_token.encrypted_refresh_token["ciphertext"] != "google-refresh-token"
