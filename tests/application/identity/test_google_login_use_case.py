import uuid
from datetime import timedelta
from unittest.mock import Mock

import pytest

from application.identity.errors import OAuthRelinkRequiresStepUp
from application.identity.oauth import GoogleLoginCommand, GoogleLoginUseCase, ProviderIdentity
from application.identity.shared.ports import NullIdentityUnitOfWork
from domain.identity.account import AccountRole, User, UserRole
from domain.identity.oauth import OAuthAccessToken, OAuthRefreshToken, OAuthToken
from domain.identity.credentials import Email
from domain.identity.oauth import OAuthProvider
from domain.shared.utils import utc_now


class RecordingUnitOfWork:
    def __init__(self):
        self.entered = False
        self.committed = False
        self.rolled_back = False

    def __enter__(self):
        self.entered = True
        return self

    def __exit__(self, exc_type, exc, traceback):
        if exc_type is not None or not self.committed:
            self.rolled_back = True
        return None

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


class FixedClock:
    def __init__(self):
        self.value = utc_now()

    def now(self):
        return self.value


class SequentialIdGenerator:
    def __init__(self):
        self.ids = [
            uuid.UUID("00000000-0000-0000-0000-000000000001"),
            uuid.UUID("00000000-0000-0000-0000-000000000002"),
            uuid.UUID("00000000-0000-0000-0000-000000000003"),
            uuid.UUID("00000000-0000-0000-0000-000000000004"),
        ]

    def new_id(self):
        return self.ids.pop(0)


def _google_command(
    *,
    email="oauth@example.com",
    google_id="google-123",
    name="OAuth User",
    first_name=None,
    last_name=None,
    access_token="google_access",
    refresh_token="google_refresh",
    expires_in=3600,
    signup_role=None,
    email_verified=True,
):
    if first_name is None or last_name is None:
        parts = name.split(maxsplit=1)
        first_name = first_name if first_name is not None else (parts[0] if parts else "Google")
        last_name = last_name if last_name is not None else (parts[1] if len(parts) > 1 else "User")
    return GoogleLoginCommand(
        identity=ProviderIdentity(
            provider=OAuthProvider.GOOGLE,
            provider_user_id=google_id,
            email=Email(email),
            first_name=first_name,
            last_name=last_name,
            email_verified=email_verified,
        ),
        access_token=OAuthAccessToken(access_token),
        refresh_token=OAuthRefreshToken(refresh_token) if refresh_token else None,
        expires_at=utc_now() + timedelta(seconds=expires_in),
        signup_role=signup_role,
    )


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
    service.create_session_tokens.return_value = ("access_token", "refresh_token")
    return service


@pytest.fixture
def mock_session_store():
    store = Mock()
    store.create_identity_session.return_value = "session-id"
    return store


@pytest.fixture
def mock_event_dispatcher():
    return Mock()


@pytest.fixture
def mock_mfa_challenge_repository():
    return Mock()


@pytest.fixture
def use_case(
    mock_user_repo,
    mock_oauth_repo,
    mock_token_service,
    mock_session_store,
    mock_event_dispatcher,
    mock_mfa_challenge_repository,
):
    return GoogleLoginUseCase(
        user_repo=mock_user_repo,
        oauth_repo=mock_oauth_repo,
        token_service=mock_token_service,
        session_store=mock_session_store,
        clock=FixedClock(),
        id_generator=SequentialIdGenerator(),
        unit_of_work=NullIdentityUnitOfWork(),
        mfa_challenge_repository=mock_mfa_challenge_repository,
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
            _google_command(
                email="new.oauth@example.com",
                name="New OAuth",
                google_id="google-123",
                signup_role=AccountRole.PLANNER,
            )
        )

        assert result.requires_2fa is False
        assert result.access == "access_token"
        assert result.refresh == "refresh_token"
        assert result.bootstrap_user is not None
        assert result.bootstrap_user["email"] == "new.oauth@example.com"
        assert mock_user_repo.save.call_count == 3
        created_user = mock_user_repo.save.call_args_list[0].args[0]
        saved_oauth_token = mock_oauth_repo.save.call_args.args[0]
        assert created_user.id == uuid.UUID("00000000-0000-0000-0000-000000000001")
        assert saved_oauth_token.id == uuid.UUID("00000000-0000-0000-0000-000000000002")
        assert created_user.created_at == use_case.clock.value

    def test_create_account_rolls_back_unit_of_work_when_oauth_save_fails(
        self,
        mock_user_repo,
        mock_oauth_repo,
        mock_token_service,
        mock_session_store,
        mock_event_dispatcher,
    ):
        unit_of_work = RecordingUnitOfWork()
        mock_user_repo.get_by_email.return_value = None
        mock_user_repo.save.side_effect = lambda u: u
        mock_oauth_repo.get_by_provider_and_user.return_value = None
        mock_oauth_repo.save.side_effect = RuntimeError("oauth write failed")
        use_case = GoogleLoginUseCase(
            user_repo=mock_user_repo,
            oauth_repo=mock_oauth_repo,
            token_service=mock_token_service,
            session_store=mock_session_store,
            clock=FixedClock(),
            id_generator=SequentialIdGenerator(),
            mfa_challenge_repository=Mock(),
            event_dispatcher=mock_event_dispatcher,
            unit_of_work=unit_of_work,
        )

        with pytest.raises(RuntimeError, match="oauth write failed"):
            use_case.execute(
                _google_command(
                    email="partial.oauth@example.com",
                    name="Partial OAuth",
                    google_id="google-partial",
                    signup_role=AccountRole.PLANNER,
                )
            )

        assert mock_user_repo.save.called is True
        assert mock_oauth_repo.save.called is True
        assert unit_of_work.entered is True
        assert unit_of_work.committed is False
        assert unit_of_work.rolled_back is True
        mock_oauth_repo.save.assert_called_once()
        mock_token_service.create_access_token.assert_not_called()
        mock_token_service.create_refresh_token.assert_not_called()

    def test_creates_vendor_when_signup_role_is_vendor(
        self,
        use_case,
        mock_user_repo,
        mock_oauth_repo,
    ):
        mock_user_repo.get_by_email.return_value = None
        saved_users = []

        def _save(user):
            saved_users.append(user)
            return user

        mock_user_repo.save.side_effect = _save
        mock_oauth_repo.get_by_provider_and_user.return_value = None

        use_case.execute(
            _google_command(
                email="vendor.oauth@example.com",
                name="Vendor OAuth",
                google_id="google-vendor",
                signup_role=AccountRole.VENDOR,
                refresh_token=None,
            )
        )

        assert saved_users[0].role is UserRole.VENDOR

    def test_oauth_signup_role_uses_register_new_self_registration_guard(
        self,
        use_case,
        mock_user_repo,
        mock_oauth_repo,
    ):
        mock_user_repo.get_by_email.return_value = None
        mock_user_repo.save.side_effect = lambda u: u
        mock_oauth_repo.get_by_provider_and_user.return_value = None

        with pytest.raises(ValueError, match="Role cannot self-register"):
            use_case.execute(
                _google_command(
                    email="admin.oauth@example.com",
                    name="Admin OAuth",
                    google_id="google-admin",
                    signup_role=AccountRole.ADMIN,
                    refresh_token=None,
                )
            )

        mock_user_repo.save.assert_not_called()
        mock_oauth_repo.save.assert_not_called()

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
            is_verified=True,
            two_factor_enabled=True,
        )
        mock_user_repo.get_by_email.return_value = user
        mock_oauth_repo.get_by_provider_and_user.return_value = None
        mock_oauth_repo.get_by_user_and_provider.return_value = None

        result = use_case.execute(
            _google_command(
                email="twofa@example.com",
                name="Two Factor",
                google_id="google-2fa",
                refresh_token=None,
            )
        )

        assert result.requires_2fa is True
        assert result.temp_token == "temp_token"
        saved_challenge = use_case.session_issuer.mfa_challenge_repository.save.call_args.args[0]
        assert saved_challenge.user_id == user.id
        mock_token_service.create_temp_token.assert_called_once_with(str(user.id), str(saved_challenge.id))
        mock_token_service.create_access_token.assert_not_called()
        mock_token_service.create_refresh_token.assert_not_called()
        mock_token_service.create_session_tokens.assert_not_called()

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
                _google_command(
                    email="mismatch@example.com",
                    name="Mismatch User",
                    google_id="google-new",
                    refresh_token=None,
                )
            )

    def test_rejects_when_google_identity_is_linked_to_other_account(
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
            is_verified=True,
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

        with pytest.raises(OAuthRelinkRequiresStepUp, match="requires step-up"):
            use_case.execute(
                _google_command(
                    email="canonical@example.com",
                    name="Canon User",
                    google_id="google-merge",
                    refresh_token="r",
                )
            )

        assert linked_elsewhere.user_id != canonical_user.id
        mock_oauth_repo.save.assert_not_called()
        mock_user_repo.save.assert_not_called()
