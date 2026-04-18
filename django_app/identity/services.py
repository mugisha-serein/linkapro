from infrastructure.repos.django_user_repository import DjangoUserRepository
from infrastructure.repos.django_oauth_token_repository import DjangoOAuthTokenRepository
from infrastructure.adapters.password_hasher import DjangoPasswordHasher
from infrastructure.adapters.jwt_token_service import JWTTokenService
from infrastructure.adapters.django_event_dispatcher import DjangoEventDispatcher
from application.identity.handlers import IdentityCommandHandlers, IdentityQueryHandlers

def get_command_handlers():
    return IdentityCommandHandlers(
        user_repo=DjangoUserRepository(),
        oauth_repo=DjangoOAuthTokenRepository(),
        password_hasher=DjangoPasswordHasher(),
        token_service=JWTTokenService(),
        event_dispatcher=DjangoEventDispatcher(),
    )

def get_query_handlers():
    return IdentityQueryHandlers(
        user_repo=DjangoUserRepository(),
    )