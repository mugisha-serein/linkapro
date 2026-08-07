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


class _KeyProvider:
    """Stateless stand-in for the Vault-backed envelope key provider."""

    _PREFIX = b"wrapped:"

    def wrap_dek(self, dek):
        return self._PREFIX + dek

    def unwrap_dek(self, wrapped):
        return wrapped[len(self._PREFIX):]


def test_new_google_email_creates_user_and_returns_session_tokens():
    dispatcher = _Dispatcher()
    key_provider = _KeyProvider()
    use_case = GoogleLoginUseCase(
        user_repo=DjangoUserRepository(),
        oauth_repo=DjangoOAuthTokenRepository(key_provider=key_provider),
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
    # Tokens are stored encrypted, never as raw plaintext.
    assert saved_oauth_token.encrypted_access_token != "google-access-token"
    assert "google-access-token" not in saved_oauth_token.encrypted_access_token
    assert "google-refresh-token" not in saved_oauth_token.encrypted_refresh_token
    assert saved_oauth_token.dek_encrypted is not None

    # A fresh repository with the same key provider decrypts the stored tokens.
    token_repo = DjangoOAuthTokenRepository(key_provider=key_provider)
    decrypted = token_repo.get_by_provider_and_user(OAuthProvider.GOOGLE, "google-new-123")
    assert decrypted is not None
    assert decrypted.access_token.raw_value == "google-access-token"
    assert decrypted.refresh_token.raw_value == "google-refresh-token"
