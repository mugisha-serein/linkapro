import uuid
from datetime import timedelta
from unittest.mock import Mock

import pytest

from application.identity.use_cases.google_login import GoogleLoginUseCase
from domain.identity.entities import OAuthToken, User, UserRole
from domain.identity.value_objects import Email, OAuthProvider
from domain.shared.utils import utc_now


@pytest.fixture
def mock_user_repo():
    return Mock()


@pytest.fixture
def mock_oauth_repo():
    return Mock()


@pytest.fixture
def mock_token_service():
    service = Mock()
    service.create_temp_token.return_value = "temp_token"
    service.create_access_token.return_value = "access_token"
    service.create_refresh_token.return_value = "refresh_token"
    return service


@pytest.fixture
def mock_event_dispatcher():
    return Mock()


@pytest.fixture
def use_case(mock_user_repo, mock_oauth_repo, mock_token_service, mock_event_dispatcher):
    return GoogleLoginUseCase(
        user_repo=mock_user_repo,
        oauth_repo=mock_oauth_repo,
        token_service=mock_token_service,
        event_dispatcher=mock_event_dispatcher,
    )


class TestGoogleLoginUseCase:
    def test_creates_new_user_and_issues_tokens(
        self,
        use_case,
        mock_user_repo,
        mock_oauth_repo,
        mock_token_service,
    ):
        mock_user_repo.get_by_email.return_value = None
        mock_user_repo.save.side_effect = lambda u: u
        mock_oauth_repo.get_by_provider_and_user.return_value = None

        result = use_case.execute(
            {
                "email": "new.oauth@example.com",
                "name": "New OAuth",
                "google_id": "google-123",
                "picture": "https://example.com/pic.png",
            },
            {
                "access_token": "google_access",
                "refresh_token": "google_refresh",
                "expires_in": 3600,
            },
        )

        assert result.requires_2fa is False
        assert result.access == "access_token"
        assert result.refresh == "refresh_token"
        assert mock_user_repo.save.call_count == 2
        mock_oauth_repo.save.assert_called_once()
        mock_token_service.create_access_token.assert_called_once()
        mock_token_service.create_refresh_token.assert_called_once()

    def test_existing_user_with_2fa_gets_temp_token(
        self,
        use_case,
        mock_user_repo,
        mock_oauth_repo,
        mock_token_service,
    ):
        user = User(
            id=uuid.uuid4(),
            email=Email("twofa@example.com"),
            password_hash=None,
            first_name="Two",
            last_name="Factor",
            role=UserRole.PLANNER,
            two_factor_enabled=True,
        )
        mock_user_repo.get_by_email.return_value = user
        mock_oauth_repo.get_by_provider_and_user.return_value = None
        mock_oauth_repo.get_by_user_and_provider.return_value = None

        result = use_case.execute(
            {
                "email": "twofa@example.com",
                "name": "Two Factor",
                "google_id": "google-2fa",
                "picture": "",
            },
            {"access_token": "google_access", "expires_in": 3600},
        )

        assert result.requires_2fa is True
        assert result.temp_token == "temp_token"
        mock_token_service.create_temp_token.assert_called_once_with(str(user.id))
        mock_token_service.create_access_token.assert_not_called()
        mock_token_service.create_refresh_token.assert_not_called()

    def test_blocks_identity_mismatch_for_existing_link(
        self,
        use_case,
        mock_user_repo,
        mock_oauth_repo,
    ):
        user = User(
            id=uuid.uuid4(),
            email=Email("mismatch@example.com"),
            password_hash=None,
            first_name="Mismatch",
            last_name="User",
            role=UserRole.PLANNER,
        )
        existing_user_link = OAuthToken(
            id=uuid.uuid4(),
            user_id=user.id,
            provider=OAuthProvider.GOOGLE,
            provider_user_id="google-old",
            access_token="old_access",
            refresh_token=None,
            expires_at=utc_now() + timedelta(hours=1),
        )
        mock_user_repo.get_by_email.return_value = user
        mock_oauth_repo.get_by_provider_and_user.return_value = None
        mock_oauth_repo.get_by_user_and_provider.return_value = existing_user_link

        with pytest.raises(ValueError, match="does not match"):
            use_case.execute(
                {
                    "email": "mismatch@example.com",
                    "name": "Mismatch User",
                    "google_id": "google-new",
                    "picture": "",
                },
                {"access_token": "google_access", "expires_in": 3600},
            )

    def test_merges_when_google_identity_is_linked_to_other_account(
        self,
        use_case,
        mock_user_repo,
        mock_oauth_repo,
    ):
        canonical_user = User(
            id=uuid.uuid4(),
            email=Email("canonical@example.com"),
            password_hash=None,
            first_name="Canon",
            last_name="User",
            role=UserRole.PLANNER,
        )
        linked_elsewhere = OAuthToken(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            provider=OAuthProvider.GOOGLE,
            provider_user_id="google-merge",
            access_token="old_access",
            refresh_token=None,
            expires_at=utc_now() + timedelta(hours=1),
        )

        mock_user_repo.get_by_email.return_value = canonical_user
        mock_oauth_repo.get_by_provider_and_user.return_value = linked_elsewhere
        mock_oauth_repo.get_by_user_and_provider.return_value = None
        mock_user_repo.save.side_effect = lambda u: u

        result = use_case.execute(
            {
                "email": "canonical@example.com",
                "name": "Canon User",
                "google_id": "google-merge",
                "picture": "",
            },
            {"access_token": "google_access", "refresh_token": "r", "expires_in": 3600},
        )

        assert result.requires_2fa is False
        assert linked_elsewhere.user_id == canonical_user.id
        mock_oauth_repo.save.assert_called_once()
