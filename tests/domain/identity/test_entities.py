import uuid
import pytest
from dataclasses import fields
from datetime import datetime, UTC
from freezegun import freeze_time

from domain.identity.entities import User, OAuthToken, UserRole
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
        assert token.access_token.raw_value == "new-access"
        assert token.refresh_token.raw_value == "new-refresh"
