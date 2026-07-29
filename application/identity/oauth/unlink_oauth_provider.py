"""Unlink an OAuth provider from an account."""

from dataclasses import dataclass
import uuid

from application.identity.errors import (
    OAuthUnlinkWouldRemoveOnlyAuthenticationMethod,
    UserNotFoundError,
)
from application.identity.shared.ports import AccountRepository, OAuthIdentityRepository
from domain.identity.oauth import OAuthProvider


@dataclass(frozen=True)
class UnlinkOAuthProviderCommand:
    user_id: uuid.UUID
    provider: OAuthProvider


class UnlinkOAuthProviderUseCase:
    def __init__(
        self,
        *,
        account_repository: AccountRepository,
        oauth_repository: OAuthIdentityRepository,
    ) -> None:
        self.account_repository = account_repository
        self.oauth_repository = oauth_repository

    def execute(self, cmd: UnlinkOAuthProviderCommand) -> None:
        user = self.account_repository.get_by_id(cmd.user_id)
        if not user:
            raise UserNotFoundError("User not found")

        linked_identities = self.oauth_repository.list_by_user(user.id)
        target_link = next(
            (identity for identity in linked_identities if identity.provider == cmd.provider),
            None,
        )
        if target_link is None:
            return

        if user.password_hash is None and len(linked_identities) <= 1:
            raise OAuthUnlinkWouldRemoveOnlyAuthenticationMethod(
                "Cannot unlink the only authentication method"
            )

        self.oauth_repository.delete_for_user(user.id, cmd.provider)


__all__ = ["UnlinkOAuthProviderCommand", "UnlinkOAuthProviderUseCase"]
