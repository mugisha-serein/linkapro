from infrastructure.identity.django_user_repository import DjangoUserRepository
from infrastructure.identity.django_oauth_token_repository import DjangoOAuthTokenRepository
from infrastructure.identity.shared.security_primitives import DjangoPasswordHasher
from infrastructure.identity.jwt_token_service import JWTTokenService
from infrastructure.identity.google_oauth_adapter import GoogleOAuthAdapter
from infrastructure.identity.django_identity_event_outbox import DjangoIdentityEventOutboxDispatcher
from infrastructure.identity.django_identity_session_store import DjangoIdentitySessionStore
from application.identity.handlers import IdentityCommandHandlers, IdentityQueryHandlers
from application.identity.use_cases.google_login import GoogleLoginUseCase
from application.identity.session_facade import IdentitySessionFacade
from application.identity.token_handlers import TokenCommandHandlers
from infrastructure.identity.shared.security_primitives import RedisTokenBlacklist

def get_command_handlers():
    return IdentityCommandHandlers(
        user_repo=DjangoUserRepository(),
        oauth_repo=DjangoOAuthTokenRepository(),
        password_hasher=DjangoPasswordHasher(),
        token_service=JWTTokenService(),
        session_store=DjangoIdentitySessionStore(),
        token_blacklist=RedisTokenBlacklist(),
        event_dispatcher=DjangoIdentityEventOutboxDispatcher(),
    )

def get_query_handlers():
    return IdentityQueryHandlers(
        user_repo=DjangoUserRepository(),
    )


def get_google_oauth_adapter() -> GoogleOAuthAdapter:
    return GoogleOAuthAdapter()


def get_google_login_use_case() -> GoogleLoginUseCase:
    return GoogleLoginUseCase(
        user_repo=DjangoUserRepository(),
        oauth_repo=DjangoOAuthTokenRepository(),
        token_service=JWTTokenService(),
        session_store=DjangoIdentitySessionStore(),
        event_dispatcher=DjangoIdentityEventOutboxDispatcher(),
    )


def get_token_handlers() -> TokenCommandHandlers:
    return TokenCommandHandlers(
        blacklist=RedisTokenBlacklist(),
        session_store=DjangoIdentitySessionStore(),
    )


def get_auth_session_facade() -> IdentitySessionFacade:
    command_handlers = get_command_handlers()
    return IdentitySessionFacade(
        command_handlers=command_handlers,
        google_login_use_case=get_google_login_use_case(),
        token_handlers=get_token_handlers(),
    )
