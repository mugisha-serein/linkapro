import uuid
import pytest
from datetime import datetime, UTC
from freezegun import freeze_time

from domain.identity.entities import User, OAuthToken, UserRole
from domain.identity.value_objects import Email, PasswordHash, OAuthProvider


class TestUserEntity:
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
        user.change_password(new_hash)
        assert user.password_hash == new_hash
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
        user.deactivate()
        assert user.is_active is False

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