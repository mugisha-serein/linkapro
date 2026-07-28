import uuid
import pytest
from dataclasses import fields
from datetime import datetime, UTC, timedelta
from freezegun import freeze_time

from domain.identity.account import (
    AccountStatus,
    AccountCannotBeActivated,
    User,
    UserActivated,
    UserDeactivated,
    UserLocked,
    UserRegistered,
    UserRestored,
    UserRole,
    UserSuspended,
    UserUnlocked,
)
from domain.identity.authentication import UserLoggedIn
from domain.identity.authorization import (
    Permission,
    RoleAssignmentDenied,
    RoleAssignmentRequiresActor,
    RoleCannotBeSelfAssigned,
    UserRoleChanged,
)
from domain.identity.credentials import UserPasswordChanged
from domain.identity.mfa import UserTwoFactorDisabled, UserTwoFactorEnabled
from domain.identity.oauth import OAuthToken
from domain.identity.oauth import UserOAuthLinked
from domain.identity.verification import UserVerified, VerificationCode, VerificationPolicy, VerificationPurpose
from domain.identity.credentials import Email, PasswordHash
from domain.identity.oauth import OAuthAccessToken, OAuthLinkingPolicy, OAuthProvider, OAuthRefreshToken


def _succeeded_email_challenge(user_id: uuid.UUID):
    code = VerificationCode("123456")
    challenge = VerificationPolicy().issue_challenge(
        user_id=user_id,
        purpose=VerificationPurpose.EMAIL,
        code=code,
    )
    VerificationPolicy().verify_challenge(challenge, code)
    challenge.pull_events()
    return challenge


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

    @pytest.mark.parametrize(
        ("field_name", "value"),
        [
            ("role", UserRole.VENDOR),
            ("status", AccountStatus.SUSPENDED),
            ("is_active", False),
            ("is_verified", True),
            ("password_hash", PasswordHash("new_hash")),
            ("auth_token_version", 2),
            ("two_factor_enabled", True),
        ],
    )
    def test_direct_sensitive_field_writes_are_blocked(self, field_name, value):
        user = User(
            id=uuid.uuid4(),
            email=Email("test@example.com"),
            password_hash=PasswordHash("hash"),
            first_name="John",
            last_name="Doe",
            role=UserRole.PLANNER,
        )

        with pytest.raises(AttributeError, match="User mutator"):
            setattr(user, field_name, value)

    def test_non_sensitive_fields_remain_directly_mutable(self):
        user = User(
            id=uuid.uuid4(),
            email=Email("test@example.com"),
            password_hash=PasswordHash("hash"),
            first_name="John",
            last_name="Doe",
            role=UserRole.PLANNER,
        )

        user.first_name = "Jane"
        user.last_login = datetime(2025, 1, 1, tzinfo=UTC)

        assert user.first_name == "Jane"
        assert user.last_login == datetime(2025, 1, 1, tzinfo=UTC)

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

    def test_change_role_updates_role_rotates_version_and_records_event(self):
        user = User(
            id=uuid.uuid4(),
            email=Email("test@example.com"),
            password_hash=PasswordHash("hash"),
            first_name="John",
            last_name="Doe",
            role=UserRole.PLANNER,
            auth_token_version=4,
        )

        actor_id = uuid.uuid4()
        user.change_role(
            UserRole.VENDOR,
            actor_user_id=actor_id,
            actor_role=UserRole.ADMIN,
        )

        assert user.role is UserRole.VENDOR
        assert user.auth_token_version == 5
        events = user.pull_events()
        assert len(events) == 1
        assert isinstance(events[0], UserRoleChanged)
        assert events[0].user_id == user.id
        assert events[0].previous_role is UserRole.PLANNER
        assert events[0].new_role is UserRole.VENDOR
        assert events[0].actor_user_id == actor_id
        assert events[0].auth_token_version == user.auth_token_version

    def test_change_role_noops_when_unchanged(self):
        user = User(
            id=uuid.uuid4(),
            email=Email("test@example.com"),
            password_hash=PasswordHash("hash"),
            first_name="John",
            last_name="Doe",
            role=UserRole.PLANNER,
            auth_token_version=4,
        )

        user.change_role("planner")

        assert user.role is UserRole.PLANNER
        assert user.auth_token_version == 4
        assert user.pull_events() == []

    def test_change_role_rejects_invalid_role(self):
        user = User(
            id=uuid.uuid4(),
            email=Email("test@example.com"),
            password_hash=PasswordHash("hash"),
            first_name="John",
            last_name="Doe",
            role=UserRole.PLANNER,
            auth_token_version=4,
        )

        with pytest.raises(ValueError):
            user.change_role(
                "owner",
                actor_user_id=uuid.uuid4(),
                actor_role=UserRole.ADMIN,
            )

        assert user.role is UserRole.PLANNER
        assert user.auth_token_version == 4
        assert user.pull_events() == []

    def test_change_role_requires_authorizing_actor_for_transition(self):
        user = User(
            id=uuid.uuid4(),
            email=Email("test@example.com"),
            password_hash=PasswordHash("hash"),
            first_name="John",
            last_name="Doe",
            role=UserRole.PLANNER,
            auth_token_version=4,
        )

        with pytest.raises(RoleAssignmentRequiresActor):
            user.change_role(UserRole.VENDOR)

        assert user.role is UserRole.PLANNER
        assert user.auth_token_version == 4
        assert user.pull_events() == []

    def test_change_role_rejects_self_assignment_to_admin(self):
        user = User(
            id=uuid.uuid4(),
            email=Email("test@example.com"),
            password_hash=PasswordHash("hash"),
            first_name="John",
            last_name="Doe",
            role=UserRole.PLANNER,
            auth_token_version=4,
        )

        with pytest.raises(RoleCannotBeSelfAssigned):
            user.change_role(
                UserRole.ADMIN,
                actor_user_id=user.id,
                actor_role=UserRole.ADMIN,
            )

        assert user.role is UserRole.PLANNER
        assert user.auth_token_version == 4
        assert user.pull_events() == []

    def test_change_role_requires_admin_assignment_permission_for_escalation(self):
        user = User(
            id=uuid.uuid4(),
            email=Email("test@example.com"),
            password_hash=PasswordHash("hash"),
            first_name="John",
            last_name="Doe",
            role=UserRole.PLANNER,
            auth_token_version=4,
        )

        with pytest.raises(RoleAssignmentDenied):
            user.change_role(
                UserRole.ADMIN,
                actor_user_id=uuid.uuid4(),
                actor_role=UserRole.ADMIN,
                permissions={Permission.ASSIGN_USER_ROLE},
            )

        assert user.role is UserRole.PLANNER
        assert user.auth_token_version == 4
        assert user.pull_events() == []

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

    def test_update_profile_validates_and_normalizes_name(self):
        user = User(
            id=uuid.uuid4(),
            email=Email("test@example.com"),
            password_hash=PasswordHash("hash"),
            first_name="John",
            last_name="Doe",
            role=UserRole.PLANNER,
        )
        user.update_profile(first_name=" Jane ", last_name=" Smith ")
        assert user.first_name == "Jane"
        assert user.last_name == "Smith"

    def test_update_profile_rejects_empty_name(self):
        user = User(
            id=uuid.uuid4(),
            email=Email("test@example.com"),
            password_hash=PasswordHash("hash"),
            first_name="John",
            last_name="Doe",
            role=UserRole.PLANNER,
        )
        with pytest.raises(ValueError, match="cannot be empty"):
            user.update_profile(first_name=" ")

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
            is_verified=True,
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
        challenge = _succeeded_email_challenge(user.id)
        user.mark_verified(challenge=challenge)
        user.mark_verified(challenge=challenge)
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
            is_verified=True,
        )
        user.activate()
        user.activate()
        events = user.pull_events()
        assert user.is_active is True
        assert len(events) == 1
        assert isinstance(events[0], UserActivated)
        assert events[0].user_id == user.id
        assert events[0].auth_token_version == user.auth_token_version

    def test_activate_rejects_unverified_account(self):
        user = User(
            id=uuid.uuid4(),
            email=Email("test@example.com"),
            password_hash=PasswordHash("hash"),
            first_name="John",
            last_name="Doe",
            role=UserRole.PLANNER,
            is_active=False,
            is_verified=False,
        )

        with pytest.raises(AccountCannotBeActivated, match="verified before activation"):
            user.activate()

        assert user.status is AccountStatus.DEACTIVATED_PENDING_VERIFICATION
        assert user.is_active is False
        assert user.is_verified is False
        assert user.pull_events() == []

    def test_account_status_transitions_record_domain_events(self):
        user = User(
            id=uuid.uuid4(),
            email=Email("test@example.com"),
            password_hash=PasswordHash("hash"),
            first_name="John",
            last_name="Doe",
            role=UserRole.PLANNER,
            is_verified=True,
            auth_token_version=2,
        )

        user.suspend("Policy review")
        assert user.status is AccountStatus.SUSPENDED
        assert user.is_active is False
        assert user.auth_token_version == 3

        user.restore()
        assert user.status is AccountStatus.ACTIVE
        assert user.is_active is True
        assert user.auth_token_version == 4

        user.lock()
        assert user.status is AccountStatus.LOCKED
        assert user.is_active is False
        assert user.auth_token_version == 5

        user.unlock()
        assert user.status is AccountStatus.ACTIVE
        assert user.is_active is True
        assert user.auth_token_version == 6

        events = user.pull_events()
        assert [type(event) for event in events] == [
            UserSuspended,
            UserRestored,
            UserLocked,
            UserUnlocked,
        ]
        assert str(events[0].reason) == "Policy review"
        assert [event.auth_token_version for event in events] == [3, 4, 5, 6]

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
        assert user.status is AccountStatus.PENDING_VERIFICATION
        assert user.is_active is True
        assert user.is_verified is False

    def test_register_new_can_create_verified_oauth_account(self):
        user = User.register_new(
            id=uuid.uuid4(),
            email=Email("test@example.com"),
            password_hash=None,
            first_name="John",
            last_name="Doe",
            role=UserRole.PLANNER,
            is_verified=True,
        )

        assert user.status is AccountStatus.ACTIVE
        assert user.is_active is True
        assert user.is_verified is True

    def test_register_new_records_user_registered_event(self):
        user = User.register_new(
            id=uuid.uuid4(),
            email=Email("test@example.com"),
            password_hash=PasswordHash("hash"),
            first_name="John",
            last_name="Doe",
            role=UserRole.PLANNER,
        )

        events = user.pull_events()
        assert len(events) == 1
        assert isinstance(events[0], UserRegistered)
        assert events[0].user_id == user.id
        assert events[0].email == user.email
        assert events[0].role is UserRole.PLANNER

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
        assert user.status is AccountStatus.ACTIVE

    @pytest.mark.parametrize(
        ("is_active", "is_verified", "expected"),
        [
            (False, False, AccountStatus.DEACTIVATED_PENDING_VERIFICATION),
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
        events = user.pull_events()
        assert len(events) == 1
        assert isinstance(events[0], UserLoggedIn)
        assert events[0].user_id == user.id
        assert events[0].occurred_at == user.last_login

    def test_oauth_link_methods_record_domain_events(self):
        user = User(
            id=uuid.uuid4(),
            email=Email("test@example.com"),
            password_hash=None,
            first_name="John",
            last_name="Doe",
            role=UserRole.PLANNER,
        )

        user.link_oauth_provider(OAuthProvider.GOOGLE)
        user.relink_oauth_provider("google")

        events = user.pull_events()
        assert [type(event) for event in events] == [UserOAuthLinked, UserOAuthLinked]
        assert [event.provider for event in events] == ["google", "google"]
        assert all(event.user_id == user.id for event in events)


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

    def test_link_to_reassigns_owner_when_policy_authorizes_relink(self):
        original_owner_id = uuid.uuid4()
        new_owner_id = uuid.uuid4()
        token = OAuthToken(
            id=uuid.uuid4(),
            user_id=original_owner_id,
            provider=OAuthProvider.GOOGLE,
            provider_user_id="12345",
            access_token="abc",
            refresh_token=None,
            expires_at=datetime(2099, 1, 1, tzinfo=UTC),
        )
        policy = OAuthLinkingPolicy().decide(
            provider=OAuthProvider.GOOGLE,
            provider_user_id="12345",
            account=type("Account", (), {"id": new_owner_id, "password_hash": None})(),
            provider_identity_link=token,
            existing_account_link=None,
            provider_email_verified=True,
        )

        token.link_to(new_owner_id, policy, occurred_at=datetime.now(UTC))

        assert token.user_id == new_owner_id

    def test_link_to_rejects_unauthorized_reassignment(self):
        token = OAuthToken(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            provider=OAuthProvider.GOOGLE,
            provider_user_id="12345",
            access_token="abc",
            refresh_token=None,
            expires_at=datetime(2099, 1, 1, tzinfo=UTC),
        )
        target_id = uuid.uuid4()
        policy = OAuthLinkingPolicy().decide(
            provider=OAuthProvider.GOOGLE,
            provider_user_id="12345",
            account=type("Account", (), {"id": target_id, "password_hash": None})(),
            provider_identity_link=None,
            existing_account_link=None,
            provider_email_verified=True,
        )

        with pytest.raises(ValueError, match="not authorized"):
            token.link_to(target_id, policy, occurred_at=datetime.now(UTC))
