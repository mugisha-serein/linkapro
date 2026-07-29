"""Revoke stored OAuth provider tokens for an account."""

from dataclasses import dataclass
import uuid

from application.identity.errors import UserNotFoundError
from application.identity.shared.ports import AccountRepository, OAuthIdentityRepository
from domain.identity.oauth import OAuthProvider


@dataclass(frozen=True)
class RevokeOAuthTokenCommand:
    user_id: uuid.UUID
    provider: OAuthProvider


class RevokeOAuthTokenUseCase:
    def __init__(
        self,
        *,
        account_repository: AccountRepository,
        oauth_repository: OAuthIdentityRepository,
    ) -> None:
        self.account_repository = account_repository
        self.oauth_repository = oauth_repository

    def execute(self, cmd: RevokeOAuthTokenCommand) -> None:
        user = self.account_repository.get_by_id(cmd.user_id)
        if not user:
            raise UserNotFoundError("User not found")
        self.oauth_repository.delete_for_user(user.id, cmd.provider)


__all__ = ["RevokeOAuthTokenCommand", "RevokeOAuthTokenUseCase"]
