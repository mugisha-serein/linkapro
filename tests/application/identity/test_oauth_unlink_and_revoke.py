from datetime import timedelta
import uuid
from unittest.mock import Mock

import pytest

from application.identity.errors import (
    OAuthUnlinkWouldRemoveOnlyAuthenticationMethod,
    UserNotFoundError,
)
from application.identity.oauth import (
    RevokeOAuthTokenCommand,
    RevokeOAuthTokenUseCase,
    UnlinkOAuthProviderCommand,
    UnlinkOAuthProviderUseCase,
)
from domain.identity.account import User, UserRole
from domain.identity.credentials import Email, PasswordHash
from domain.identity.oauth import OAuthProvider, OAuthToken
from domain.shared.utils import utc_now


def _user(*, password_hash=None) -> User:
    return User(
        id=uuid.uuid4(),
        email=Email("user@example.com"),
        password_hash=password_hash,
        first_name="OAuth",
        last_name="User",
        role=UserRole.PLANNER,
        is_verified=True,
    )


def _oauth_link(user_id: uuid.UUID, provider: OAuthProvider = OAuthProvider.GOOGLE) -> OAuthToken:
    return OAuthToken(
        id=uuid.uuid4(),
        user_id=user_id,
        provider=provider,
        provider_user_id=f"{provider.value}-user",
        access_token="provider-access-token",
        refresh_token="provider-refresh-token",
        expires_at=utc_now() + timedelta(hours=1),
    )


def test_unlink_oauth_provider_blocks_passwordless_account_losing_only_auth_method():
    user = _user(password_hash=None)
    account_repository = Mock()
    account_repository.get_by_id.return_value = user
    oauth_repository = Mock()
    oauth_repository.list_by_user.return_value = (_oauth_link(user.id),)

    use_case = UnlinkOAuthProviderUseCase(
        account_repository=account_repository,
        oauth_repository=oauth_repository,
    )

    with pytest.raises(
        OAuthUnlinkWouldRemoveOnlyAuthenticationMethod,
        match="only authentication method",
    ):
        use_case.execute(UnlinkOAuthProviderCommand(user_id=user.id, provider=OAuthProvider.GOOGLE))

    oauth_repository.delete_for_user.assert_not_called()


def test_unlink_oauth_provider_allows_account_with_password():
    user = _user(password_hash=PasswordHash("hashed-password"))
    account_repository = Mock()
    account_repository.get_by_id.return_value = user
    oauth_repository = Mock()
    oauth_repository.list_by_user.return_value = (_oauth_link(user.id),)

    use_case = UnlinkOAuthProviderUseCase(
        account_repository=account_repository,
        oauth_repository=oauth_repository,
    )

    use_case.execute(UnlinkOAuthProviderCommand(user_id=user.id, provider=OAuthProvider.GOOGLE))

    oauth_repository.delete_for_user.assert_called_once_with(user.id, OAuthProvider.GOOGLE)


def test_unlink_oauth_provider_is_idempotent_when_provider_is_not_linked():
    user = _user(password_hash=None)
    account_repository = Mock()
    account_repository.get_by_id.return_value = user
    oauth_repository = Mock()
    oauth_repository.list_by_user.return_value = ()

    use_case = UnlinkOAuthProviderUseCase(
        account_repository=account_repository,
        oauth_repository=oauth_repository,
    )

    use_case.execute(UnlinkOAuthProviderCommand(user_id=user.id, provider=OAuthProvider.GOOGLE))

    oauth_repository.delete_for_user.assert_not_called()


def test_unlink_oauth_provider_rejects_unknown_user():
    account_repository = Mock()
    account_repository.get_by_id.return_value = None
    oauth_repository = Mock()
    user_id = uuid.uuid4()

    use_case = UnlinkOAuthProviderUseCase(
        account_repository=account_repository,
        oauth_repository=oauth_repository,
    )

    with pytest.raises(UserNotFoundError, match="User not found"):
        use_case.execute(UnlinkOAuthProviderCommand(user_id=user_id, provider=OAuthProvider.GOOGLE))

    oauth_repository.list_by_user.assert_not_called()
    oauth_repository.delete_for_user.assert_not_called()


def test_revoke_oauth_token_removes_stored_provider_token():
    user = _user(password_hash=None)
    account_repository = Mock()
    account_repository.get_by_id.return_value = user
    oauth_repository = Mock()

    use_case = RevokeOAuthTokenUseCase(
        account_repository=account_repository,
        oauth_repository=oauth_repository,
    )

    use_case.execute(RevokeOAuthTokenCommand(user_id=user.id, provider=OAuthProvider.GOOGLE))

    oauth_repository.delete_for_user.assert_called_once_with(user.id, OAuthProvider.GOOGLE)


def test_revoke_oauth_token_rejects_unknown_user():
    account_repository = Mock()
    account_repository.get_by_id.return_value = None
    oauth_repository = Mock()
    user_id = uuid.uuid4()

    use_case = RevokeOAuthTokenUseCase(
        account_repository=account_repository,
        oauth_repository=oauth_repository,
    )

    with pytest.raises(UserNotFoundError, match="User not found"):
        use_case.execute(RevokeOAuthTokenCommand(user_id=user_id, provider=OAuthProvider.GOOGLE))

    oauth_repository.delete_for_user.assert_not_called()
