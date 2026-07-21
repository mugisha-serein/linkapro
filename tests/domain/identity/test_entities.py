import uuid
import pytest
from dataclasses import fields
from datetime import datetime, UTC, timedelta
from freezegun import freeze_time

from domain.identity.entities import AccountStatus, User, OAuthToken, UserRole
from domain.identity.events import (
    UserActivated,
    UserDeactivated,
    UserPasswordChanged,
    UserTwoFactorDisabled,
    UserTwoFactorEnabled,
    UserVerified,
)
from domain.identity.value_objects import (
    Email,
    OAuthAccessToken,
    OAuthProvider,
    OAuthRefreshToken,
    PasswordHash,
)


class TestUserEntity:
    def test_has_only_one_auth_token_version_field(self):
        field_names = [field.name for field in fields(User)]
        assert field_names.count("auth_token_version") == 1

    def test_create_user_with_valid_data(self):
        user_id = uuid.uuid4()
        email = Email("test@example.com")
        pwd_hash = PasswordHash("hashed_secret")
        user = User(
            id=user_id,
            email=email,
            password_hash=pwd_hash,
            first_name="John",
            last_name="Doe",
            role=UserRole.PLANNER,
        )
        assert user.id == user_id
        assert user.email == email
        assert user.is_active is True
        assert user.is_verified is False

    @pytest.mark.parametrize(
        ("first_name", "last_name"),
        [("", "Doe"), ("   ", "Doe"), ("John", ""), ("John", "   ")],
    )
    def test_direct_user_construction_rejects_empty_names(self, first_name, last_name):
        with pytest.raises(ValueError, match="cannot be empty"):
            User(
                id=uuid.uuid4(),
                email=Email("test@example.com"),
                password_hash=PasswordHash("hash"),
                first_name=first_name,
                last_name=last_name,
                role=UserRole.PLANNER,
            )

    def test_direct_user_construction_strips_names_and_coerces_role(self):
        user = User(
            id=uuid.uuid4(),
            email=Email("test@example.com"),
            password_hash=PasswordHash("hash"),
            first_name=" John ",
            last_name=" Doe ",
            role="planner",
        )
        assert user.first_name == "John"
        assert user.last_name == "Doe"
        assert user.role is UserRole.PLANNER

    def test_direct_user_construction_rejects_negative_auth_token_version(self):
        with pytest.raises(ValueError, match="Auth token version"):
            User(
                id=uuid.uuid4(),
                email=Email("test@example.com"),
                password_hash=PasswordHash("hash"),
                first_name="John",
                last_name="Doe",
                role=UserRole.PLANNER,
                auth_token_version=-1,
            )

    @pytest.mark.parametrize("field_name", ["created_at", "updated_at", "last_login"])
    def test_direct_user_construction_rejects_naive_datetimes(self, field_name):
        kwargs = {
            "id": uuid.uuid4(),
            "email": Email("test@example.com"),
            "password_hash": PasswordHash("hash"),
            "first_name": "John",
            "last_name": "Doe",
            "role": UserRole.PLANNER,
        }
        kwargs[field_name] = datetime(2025, 1, 1)
        with pytest.raises(ValueError, match=field_name):
            User(**kwargs)

    @freeze_time("2025-01-01 12:00:00")
    def test_change_password_updates_hash_and_timestamp(self):
        user = User(
            id=uuid.uuid4(),
            email=Email("test@example.com"),
            password_hash=PasswordHash("old"),
            first_name="John",
            last_name="Doe",
            role=UserRole.PLANNER,
            created_at=datetime(2024, 1, 1, tzinfo=UTC),
            updated_at=datetime(2024, 1, 1, tzinfo=UTC),
        )
        new_hash = PasswordHash("new_hashed")
        original_version = user.auth_token_version
        user.change_password(new_hash)
        assert user.password_hash == new_hash
        assert user.updated_at == datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
        assert user.auth_token_version == original_version + 1

    def test_change_password_records_domain_event(self):
        user = User(
            id=uuid.uuid4(),
            email=Email("test@example.com"),
            password_hash=PasswordHash("old"),
            first_name="John",
            last_name="Doe",
            role=UserRole.PLANNER,
        )
        user.change_password(PasswordHash("new"))
        events = user.pull_events()
        assert len(events) == 1
        assert isinstance(events[0], UserPasswordChanged)
        assert events[0].user_id == user.id
        assert events[0].auth_token_version == user.auth_token_version
        assert user.pull_events() == []

    def test_rotate_auth_token_version_updates_timestamp(self):
        user = User(
            id=uuid.uuid4(),
            email=Email("test@example.com"),
            password_hash=PasswordHash("hash"),
            first_name="John",
            last_name="Doe",
            role=UserRole.PLANNER,
            auth_token_version=2,
            updated_at=datetime(2024, 1, 1, tzinfo=UTC),
        )
        with freeze_time("2025-01-01 12:00:00"):
            user.rotate_auth_token_version()
        assert user.auth_token_version == 3
        assert user.updated_at == datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)

    def test_deactivate_user(self):
        user = User(
            id=uuid.uuid4(),
            email=Email("test@example.com"),
            password_hash=PasswordHash("hash"),
            first_name="John",
            last_name="Doe",
            role=UserRole.PLANNER,
        )
        original_version = user.auth_token_version
        user.deactivate()
        assert user.is_active is False
        assert user.auth_token_version == original_version + 1

    def test_deactivation_records_domain_event(self):
        user = User(
            id=uuid.uuid4(),
            email=Email("test@example.com"),
            password_hash=PasswordHash("hash"),
            first_name="John",
            last_name="Doe",
            role=UserRole.PLANNER,
        )
        user.deactivate()
        events = user.pull_events()
        assert len(events) == 1
        assert isinstance(events[0], UserDeactivated)
        assert events[0].user_id == user.id
        assert events[0].auth_token_version == user.auth_token_version

    def test_deactivate_only_rotates_once_when_repeated(self):
        user = User(
            id=uuid.uuid4(),
            email=Email("test@example.com"),
            password_hash=PasswordHash("hash"),
            first_name="John",
            last_name="Doe",
            role=UserRole.PLANNER,
            auth_token_version=7,
        )
        user.deactivate()
        user.deactivate()
        assert user.is_active is False
        assert user.auth_token_version == 8
        events = user.pull_events()
        assert len(events) == 1
        assert isinstance(events[0], UserDeactivated)

    def test_disable_two_factor_rotates_token_version(self):
        user = User(
            id=uuid.uuid4(),
            email=Email("test@example.com"),
            password_hash=PasswordHash("hash"),
            first_name="John",
            last_name="Doe",
            role=UserRole.PLANNER,
            two_factor_enabled=True,
            auth_token_version=4,
        )
        user.disable_two_factor()
        assert user.two_factor_enabled is False
        assert user.auth_token_version == 5

    def test_disable_two_factor_only_rotates_when_enabled(self):
        user = User(
            id=uuid.uuid4(),
            email=Email("test@example.com"),
            password_hash=PasswordHash("hash"),
            first_name="John",
            last_name="Doe",
            role=UserRole.PLANNER,
            two_factor_enabled=True,
            auth_token_version=4,
        )
        user.disable_two_factor()
        user.disable_two_factor()
        assert user.two_factor_enabled is False
        assert user.auth_token_version == 5
        events = user.pull_events()
        assert len(events) == 1
        assert isinstance(events[0], UserTwoFactorDisabled)

    def test_enable_two_factor_updates_state(self):
        user = User(
            id=uuid.uuid4(),
            email=Email("test@example.com"),
            password_hash=PasswordHash("hash"),
            first_name="John",
            last_name="Doe",
            role=UserRole.PLANNER,
        )
        user.enable_two_factor()
        assert user.two_factor_enabled is True

    def test_enable_two_factor_rotates_once_when_state_changes(self):
        user = User(
            id=uuid.uuid4(),
            email=Email("test@example.com"),
            password_hash=PasswordHash("hash"),
            first_name="John",
            last_name="Doe",
            role=UserRole.PLANNER,
            auth_token_version=3,
        )
        user.enable_two_factor()
        user.enable_two_factor()
        assert user.two_factor_enabled is True
        assert user.auth_token_version == 4
        events = user.pull_events()
        assert len(events) == 1
        assert isinstance(events[0], UserTwoFactorEnabled)

    def test_activate_is_idempotent(self):
        user = User(
            id=uuid.uuid4(),
            email=Email("test@example.com"),
            password_hash=PasswordHash("hash"),
            first_name="John",
            last_name="Doe",
            role=UserRole.PLANNER,
            is_active=False,
            updated_at=datetime(2024, 1, 1, tzinfo=UTC),
        )
        with freeze_time("2025-01-01 12:00:00"):
            user.activate()
        first_updated_at = user.updated_at
        assert user.is_active is True
        assert user.auth_token_version == 0

        with freeze_time("2026-01-01 12:00:00"):
            user.activate()
        assert user.is_active is True
        assert user.updated_at == first_updated_at
        assert user.auth_token_version == 0

    def test_mark_verified_records_domain_event_once(self):
        user = User(
            id=uuid.uuid4(),
            email=Email("test@example.com"),
            password_hash=PasswordHash("hash"),
            first_name="John",
            last_name="Doe",
            role=UserRole.PLANNER,
            is_verified=False,
        )
        user.mark_verified()
        user.mark_verified()
        events = user.pull_events()
        assert user.is_verified is True
        assert len(events) == 1
        assert isinstance(events[0], UserVerified)
        assert events[0].user_id == user.id
        assert events[0].auth_token_version == user.auth_token_version

    def test_activate_records_domain_event_once(self):
        user = User(
            id=uuid.uuid4(),
            email=Email("test@example.com"),
            password_hash=PasswordHash("hash"),
            first_name="John",
            last_name="Doe",
            role=UserRole.PLANNER,
            is_active=False,
        )
        user.activate()
        user.activate()
        events = user.pull_events()
        assert user.is_active is True
        assert len(events) == 1
        assert isinstance(events[0], UserActivated)
        assert events[0].user_id == user.id
        assert events[0].auth_token_version == user.auth_token_version

    def test_two_factor_mutations_record_domain_events(self):
        user = User(
            id=uuid.uuid4(),
            email=Email("test@example.com"),
            password_hash=PasswordHash("hash"),
            first_name="John",
            last_name="Doe",
            role=UserRole.PLANNER,
        )
        user.enable_two_factor()
        user.disable_two_factor()
        events = user.pull_events()
        assert [type(event) for event in events] == [
            UserTwoFactorEnabled,
            UserTwoFactorDisabled,
        ]
        assert all(event.user_id == user.id for event in events)
        assert [event.auth_token_version for event in events] == [1, 2]

    def test_admin_cannot_self_register(self):
        assert UserRole.ADMIN.can_self_register() is False
        assert UserRole.PLANNER.can_self_register() is True
        assert UserRole.VENDOR.can_self_register() is True
        assert UserRole.ADMIN not in UserRole.public_registration_roles()

    @pytest.mark.parametrize("role", [UserRole.PLANNER, UserRole.VENDOR])
    def test_register_new_allows_public_roles(self, role):
        user = User.register_new(
            id=uuid.uuid4(),
            email=Email("test@example.com"),
            password_hash=PasswordHash("hash"),
            first_name="John",
            last_name="Doe",
            role=role,
        )
        assert user.role is role

    def test_register_new_rejects_admin(self):
        with pytest.raises(ValueError, match="cannot self-register"):
            User.register_new(
                id=uuid.uuid4(),
                email=Email("admin@example.com"),
                password_hash=PasswordHash("hash"),
                first_name="Admin",
                last_name="User",
                role=UserRole.ADMIN,
            )

    def test_rehydrate_allows_existing_admin_users(self):
        user = User.rehydrate(
            id=uuid.uuid4(),
            email=Email("admin@example.com"),
            password_hash=PasswordHash("hash"),
            first_name="Admin",
            last_name="User",
            role=UserRole.ADMIN,
            is_active=True,
            is_verified=True,
            created_at=datetime(2024, 1, 1, tzinfo=UTC),
            updated_at=datetime(2024, 1, 1, tzinfo=UTC),
        )
        assert user.role is UserRole.ADMIN

    @pytest.mark.parametrize(
        ("is_active", "is_verified", "expected"),
        [
            (False, False, AccountStatus.DEACTIVATED),
            (False, True, AccountStatus.DEACTIVATED),
            (True, False, AccountStatus.PENDING_VERIFICATION),
            (True, True, AccountStatus.ACTIVE),
        ],
    )
    def test_account_status(self, is_active, is_verified, expected):
        user = User(
            id=uuid.uuid4(),
            email=Email("test@example.com"),
            password_hash=PasswordHash("hash"),
            first_name="John",
            last_name="Doe",
            role=UserRole.PLANNER,
            is_active=is_active,
            is_verified=is_verified,
        )
        assert user.account_status() is expected

    @pytest.mark.parametrize(
        ("first_name", "last_name"),
        [("", "Doe"), ("   ", "Doe"), ("John", ""), ("John", "   ")],
    )
    def test_register_new_rejects_empty_names(self, first_name, last_name):
        with pytest.raises(ValueError, match="cannot be empty"):
            User.register_new(
                id=uuid.uuid4(),
                email=Email("test@example.com"),
                password_hash=PasswordHash("hash"),
                first_name=first_name,
                last_name=last_name,
                role=UserRole.PLANNER,
            )

    def test_record_login_sets_last_login(self):
        user = User(
            id=uuid.uuid4(),
            email=Email("test@example.com"),
            password_hash=PasswordHash("hash"),
            first_name="John",
            last_name="Doe",
            role=UserRole.PLANNER,
        )
        with freeze_time("2025-01-01"):
            user.record_login()
        assert user.last_login == datetime(2025, 1, 1, tzinfo=UTC)


class TestOAuthTokenEntity:
    def test_is_expired_returns_true_when_expired(self):
        token = OAuthToken(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            provider=OAuthProvider.GOOGLE,
            provider_user_id="12345",
            access_token="abc",
            refresh_token=None,
            expires_at=datetime(2020, 1, 1, tzinfo=UTC),
        )
        assert token.is_expired() is True

    def test_is_expired_returns_false_when_valid(self):
        token = OAuthToken(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            provider=OAuthProvider.GOOGLE,
            provider_user_id="12345",
            access_token="abc",
            refresh_token=None,
            expires_at=datetime(2099, 1, 1, tzinfo=UTC),
        )
        assert token.is_expired() is False
        assert isinstance(token.access_token, OAuthAccessToken)

    def test_close_to_expiry_is_expired_with_buffer(self):
        with freeze_time("2025-01-01 12:00:00"):
            token = OAuthToken(
                id=uuid.uuid4(),
                user_id=uuid.uuid4(),
                provider=OAuthProvider.GOOGLE,
                provider_user_id="12345",
                access_token="abc",
                refresh_token=None,
                expires_at=datetime(2025, 1, 1, 12, 0, 30, tzinfo=UTC),
            )
            assert token.is_expired() is False
            assert token.should_refresh(buffer_seconds=60) is True
            assert token.should_refresh() is True

    def test_negative_expiry_buffer_is_rejected(self):
        token = OAuthToken(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            provider=OAuthProvider.GOOGLE,
            provider_user_id="12345",
            access_token="abc",
            refresh_token=None,
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
        with pytest.raises(ValueError, match="buffer"):
            token.should_refresh(buffer_seconds=-1)

    def test_expires_at_must_be_timezone_aware(self):
        with pytest.raises(ValueError, match="timezone-aware"):
            OAuthToken(
                id=uuid.uuid4(),
                user_id=uuid.uuid4(),
                provider=OAuthProvider.GOOGLE,
                provider_user_id="12345",
                access_token="abc",
                refresh_token=None,
                expires_at=datetime(2099, 1, 1),
            )

    def test_provider_user_id_must_not_be_empty(self):
        with pytest.raises(ValueError, match="Provider user ID"):
            OAuthToken(
                id=uuid.uuid4(),
                user_id=uuid.uuid4(),
                provider=OAuthProvider.GOOGLE,
                provider_user_id="   ",
                access_token="abc",
                refresh_token=None,
                expires_at=datetime(2099, 1, 1, tzinfo=UTC),
            )

    def test_repr_does_not_expose_tokens(self):
        access_token = "access-token-secret"
        refresh_token = "refresh-token-secret"
        token = OAuthToken(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            provider=OAuthProvider.GOOGLE,
            provider_user_id="12345",
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=datetime(2099, 1, 1, tzinfo=UTC),
        )
        token_repr = repr(token)
        assert access_token not in token_repr
        assert refresh_token not in token_repr

    def test_update_tokens_keeps_secret_value_objects(self):
        token = OAuthToken(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            provider=OAuthProvider.GOOGLE,
            provider_user_id="12345",
            access_token=OAuthAccessToken("old-access"),
            refresh_token=OAuthRefreshToken("old-refresh"),
            expires_at=datetime(2020, 1, 1, tzinfo=UTC),
        )
        token.update_tokens(
            access_token="new-access",
            refresh_token="new-refresh",
            expires_at=datetime(2099, 1, 1, tzinfo=UTC),
        )
        assert isinstance(token.access_token, OAuthAccessToken)
        assert isinstance(token.refresh_token, OAuthRefreshToken)
        assert token.access_token.reveal_for_provider_sync() == "new-access"
        assert token.refresh_token.reveal_for_provider_sync() == "new-refresh"

    def test_update_tokens_requires_timezone_aware_expiry(self):
        token = OAuthToken(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            provider=OAuthProvider.GOOGLE,
            provider_user_id="12345",
            access_token=OAuthAccessToken("old-access"),
            refresh_token=OAuthRefreshToken("old-refresh"),
            expires_at=datetime(2020, 1, 1, tzinfo=UTC),
        )
        with pytest.raises(ValueError, match="timezone-aware"):
            token.update_tokens(
                access_token="new-access",
                refresh_token="new-refresh",
                expires_at=datetime(2099, 1, 1),
            )
