"""Identity account aggregate.

The identity ``User`` aggregate remains a mutable dataclass for now because its
repository and application handlers persist in-place state changes directly.
Vendor aggregates moved to a stricter immutable/candidate-transition style, but
changing identity to that model is a larger migration; keeping this note makes
the difference intentional rather than architectural drift.
"""
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import ClassVar, Optional

from domain.identity.credentials import Email, PasswordHash
from domain.identity.shared.aggregate_root import AggregateRoot
from domain.identity.shared.clock import SystemClock

from .account_rules import ensure_account_can_be_activated
from .account_role import UserRole
from .person_name import PersonName


_system_clock = SystemClock()


def _now_or_system(now: datetime | None) -> datetime:
    return now if now is not None else _system_clock.now()


class AccountStatus(str, Enum):
    PENDING_VERIFICATION = "pending_verification"
    ACTIVE = "active"
    DEACTIVATED = "deactivated"
    DEACTIVATED_PENDING_VERIFICATION = "deactivated_pending_verification"
    SUSPENDED = "suspended"
    LOCKED = "locked"


def _status_from_legacy_flags(is_active: bool, is_verified: bool) -> AccountStatus:
    if is_active and is_verified:
        return AccountStatus.ACTIVE
    if is_active and not is_verified:
        return AccountStatus.PENDING_VERIFICATION
    if not is_active and is_verified:
        return AccountStatus.DEACTIVATED
    return AccountStatus.DEACTIVATED_PENDING_VERIFICATION


@dataclass(init=False)
class User(AggregateRoot):
    _PROTECTED_MUTATION_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "role",
            "status",
            "is_active",
            "is_verified",
            "password_hash",
            "auth_token_version",
            "two_factor_enabled",
        }
    )

    id: uuid.UUID
    email: Email
    password_hash: Optional[PasswordHash]
    first_name: str
    last_name: str
    role: UserRole
    two_factor_enabled: bool = False
    auth_token_version: int = 0
    status: AccountStatus = AccountStatus.PENDING_VERIFICATION
    created_at: datetime = field(default_factory=_system_clock.now)
    updated_at: datetime = field(default_factory=_system_clock.now)
    last_login: Optional[datetime] = None

    def __init__(
        self,
        *,
        id: uuid.UUID,
        email: Email,
        password_hash: Optional[PasswordHash],
        first_name: str,
        last_name: str,
        role: UserRole | str,
        two_factor_enabled: bool = False,
        auth_token_version: int = 0,
        status: AccountStatus | str | None = None,
        is_active: bool = True,
        is_verified: bool = False,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
        last_login: Optional[datetime] = None,
    ) -> None:
        object.__setattr__(self, "_events", [])
        object.__setattr__(self, "_hydrating", True)
        object.__setattr__(self, "id", id)
        object.__setattr__(self, "email", email)
        object.__setattr__(self, "password_hash", password_hash)
        object.__setattr__(self, "first_name", first_name)
        object.__setattr__(self, "last_name", last_name)
        object.__setattr__(self, "role", role)
        object.__setattr__(self, "two_factor_enabled", two_factor_enabled)
        object.__setattr__(self, "auth_token_version", auth_token_version)
        object.__setattr__(
            self,
            "status",
            AccountStatus(status) if status is not None else _status_from_legacy_flags(is_active, is_verified),
        )
        object.__setattr__(self, "created_at", created_at or _system_clock.now())
        object.__setattr__(self, "updated_at", updated_at or _system_clock.now())
        object.__setattr__(self, "last_login", last_login)
        self.__post_init__()

    def __setattr__(self, name: str, value) -> None:
        if (
            name in self._PROTECTED_MUTATION_FIELDS
            and "_events" in self.__dict__
            and not self.__dict__.get("_hydrating", True)
        ):
            raise AttributeError(f"{name} must be changed through a User mutator")
        super().__setattr__(name, value)

    def __post_init__(self) -> None:
        try:
            self.role = UserRole(self.role)
            self.status = AccountStatus(self.status)
            name = PersonName(self.first_name, self.last_name)
            self.first_name = name.first_name
            self.last_name = name.last_name
            if self.auth_token_version < 0:
                raise ValueError("Auth token version cannot be negative")
            self._validate_timezone_aware(self.created_at, "created_at")
            self._validate_timezone_aware(self.updated_at, "updated_at")
            if self.last_login is not None:
                self._validate_timezone_aware(self.last_login, "last_login")
        finally:
            object.__setattr__(self, "_hydrating", False)

    @property
    def is_active(self) -> bool:
        return self.status in {
            AccountStatus.ACTIVE,
            AccountStatus.PENDING_VERIFICATION,
        }

    @property
    def is_verified(self) -> bool:
        return self.status in {
            AccountStatus.ACTIVE,
            AccountStatus.DEACTIVATED,
            AccountStatus.SUSPENDED,
            AccountStatus.LOCKED,
        }

    @staticmethod
    def _validate_timezone_aware(value: datetime, field_name: str) -> None:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(f"{field_name} must be timezone-aware")

    @classmethod
    def register_new(
        cls,
        *,
        id: uuid.UUID,
        email: Email,
        password_hash: Optional[PasswordHash],
        first_name: str,
        last_name: str,
        role: UserRole,
        is_verified: bool = False,
        now: datetime | None = None,
    ) -> "User":
        from .account_events import UserRegistered

        role = UserRole(role)
        if not role.can_self_register():
            raise ValueError("Role cannot self-register")
        occurred_at = _now_or_system(now)
        user = cls(
            id=id,
            email=email,
            password_hash=password_hash,
            first_name=first_name,
            last_name=last_name,
            role=role,
            status=AccountStatus.ACTIVE if is_verified else AccountStatus.PENDING_VERIFICATION,
            created_at=occurred_at,
            updated_at=occurred_at,
        )
        user._record_event(
            UserRegistered(
                user_id=user.id,
                email=user.email,
                role=user.role,
                occurred_at=user.created_at,
            )
        )
        return user

    @classmethod
    def rehydrate(
        cls,
        *,
        id: uuid.UUID,
        email: Email,
        password_hash: Optional[PasswordHash],
        first_name: str,
        last_name: str,
        role: UserRole | str,
        two_factor_enabled: bool = False,
        auth_token_version: int = 0,
        status: AccountStatus | str | None = None,
        is_active: bool = True,
        is_verified: bool = False,
        created_at: datetime,
        updated_at: datetime,
        last_login: Optional[datetime] = None,
    ) -> "User":
        return cls(
            id=id,
            email=email,
            password_hash=password_hash,
            first_name=first_name,
            last_name=last_name,
            role=role,
            two_factor_enabled=two_factor_enabled,
            auth_token_version=auth_token_version,
            status=status,
            is_active=is_active,
            is_verified=is_verified,
            created_at=created_at,
            updated_at=updated_at,
            last_login=last_login,
        )

    def rotate_auth_token_version(self, now: datetime | None = None) -> None:
        object.__setattr__(self, "auth_token_version", self.auth_token_version + 1)
        self.updated_at = _now_or_system(now)

    def change_password(
        self,
        new_password_hash: PasswordHash,
        now: datetime | None = None,
        *,
        plain_password=None,
        password_history=None,
        password_verifier=None,
    ) -> None:
        """Update password hash and record change."""
        from domain.identity.credentials import UserPasswordChanged

        occurred_at = _now_or_system(now)
        if password_history is not None:
            if plain_password is None or password_verifier is None:
                raise ValueError("Password history checks require the plain password and verifier")
            password_history.ensure_not_reused(plain_password, password_verifier)
        object.__setattr__(self, "password_hash", new_password_hash)
        self.rotate_auth_token_version(occurred_at)
        self._record_event(
            UserPasswordChanged(
                user_id=self.id,
                occurred_at=self.updated_at,
                auth_token_version=self.auth_token_version,
            )
        )

    def mark_verified(self, *, challenge, now: datetime | None = None) -> None:
        from domain.identity.verification import UserVerified, VerificationPolicy, VerificationPurpose

        if self.is_verified:
            return
        VerificationPolicy().ensure_terminal_challenge_succeeded(
            challenge,
            purpose=VerificationPurpose.EMAIL,
        )
        occurred_at = _now_or_system(now)
        object.__setattr__(self, "status", AccountStatus.ACTIVE)
        self.updated_at = occurred_at
        self._record_event(
            UserVerified(
                user_id=self.id,
                occurred_at=self.updated_at,
                auth_token_version=self.auth_token_version,
            )
        )

    def deactivate(
        self,
        now: datetime | None = None,
        *,
        actor_user_id: uuid.UUID | None = None,
        reason: object | None = None,
    ) -> None:
        from .account_events import UserDeactivated

        if self.status in {
            AccountStatus.DEACTIVATED,
            AccountStatus.DEACTIVATED_PENDING_VERIFICATION,
        }:
            return
        occurred_at = _now_or_system(now)
        next_status = (
            AccountStatus.DEACTIVATED
            if self.is_verified
            else AccountStatus.DEACTIVATED_PENDING_VERIFICATION
        )
        object.__setattr__(self, "status", next_status)
        self.rotate_auth_token_version(occurred_at)
        self._record_event(
            UserDeactivated(
                user_id=self.id,
                actor_user_id=actor_user_id,
                reason=reason,
                occurred_at=self.updated_at,
                auth_token_version=self.auth_token_version,
            )
        )

    def activate(
        self,
        now: datetime | None = None,
        *,
        actor_user_id: uuid.UUID | None = None,
        reason: object | None = None,
    ) -> None:
        from .account_events import UserActivated

        if self.status is AccountStatus.ACTIVE:
            return
        ensure_account_can_be_activated(is_verified=self.is_verified)
        occurred_at = _now_or_system(now)
        object.__setattr__(self, "status", AccountStatus.ACTIVE)
        self.updated_at = occurred_at
        self._record_event(
            UserActivated(
                user_id=self.id,
                actor_user_id=actor_user_id,
                reason=reason,
                occurred_at=self.updated_at,
                auth_token_version=self.auth_token_version,
            )
        )

    def suspend(
        self,
        reason: str,
        now: datetime | None = None,
        *,
        actor_user_id: uuid.UUID | None = None,
    ) -> None:
        from .account_events import UserSuspended

        if self.status is AccountStatus.SUSPENDED:
            return
        ensure_account_can_be_activated(is_verified=self.is_verified)
        occurred_at = _now_or_system(now)
        object.__setattr__(self, "status", AccountStatus.SUSPENDED)
        self.rotate_auth_token_version(occurred_at)
        self._record_event(
            UserSuspended(
                user_id=self.id,
                reason=reason,
                actor_user_id=actor_user_id,
                occurred_at=self.updated_at,
                auth_token_version=self.auth_token_version,
            )
        )

    def restore(
        self,
        now: datetime | None = None,
        *,
        actor_user_id: uuid.UUID | None = None,
        reason: object | None = None,
    ) -> None:
        from .account_events import UserRestored

        if self.status is AccountStatus.ACTIVE:
            return
        ensure_account_can_be_activated(is_verified=self.is_verified)
        occurred_at = _now_or_system(now)
        object.__setattr__(self, "status", AccountStatus.ACTIVE)
        self.rotate_auth_token_version(occurred_at)
        self._record_event(
            UserRestored(
                user_id=self.id,
                actor_user_id=actor_user_id,
                reason=reason,
                occurred_at=self.updated_at,
                auth_token_version=self.auth_token_version,
            )
        )

    def lock(self, now: datetime | None = None) -> None:
        from .account_events import UserLocked

        if self.status is AccountStatus.LOCKED:
            return
        ensure_account_can_be_activated(is_verified=self.is_verified)
        occurred_at = _now_or_system(now)
        object.__setattr__(self, "status", AccountStatus.LOCKED)
        self.rotate_auth_token_version(occurred_at)
        self._record_event(
            UserLocked(
                user_id=self.id,
                occurred_at=self.updated_at,
                auth_token_version=self.auth_token_version,
            )
        )

    def unlock(
        self,
        now: datetime | None = None,
        *,
        actor_user_id: uuid.UUID | None = None,
        reason: object | None = None,
    ) -> None:
        from .account_events import UserUnlocked

        if self.status is AccountStatus.ACTIVE:
            return
        ensure_account_can_be_activated(is_verified=self.is_verified)
        occurred_at = _now_or_system(now)
        object.__setattr__(self, "status", AccountStatus.ACTIVE)
        self.rotate_auth_token_version(occurred_at)
        self._record_event(
            UserUnlocked(
                user_id=self.id,
                actor_user_id=actor_user_id,
                reason=reason,
                occurred_at=self.updated_at,
                auth_token_version=self.auth_token_version,
            )
        )

    def change_role(
        self,
        new_role: UserRole,
        *,
        actor_user_id: uuid.UUID | None = None,
        actor_role: UserRole | str | None = None,
        permissions=None,
        reason=None,
        now: datetime | None = None,
    ) -> None:
        from domain.identity.authorization import RoleAssignmentContext, RoleAssignmentPolicy, UserRoleChanged

        new_role = UserRole(new_role)
        if new_role is self.role:
            return
        context = RoleAssignmentContext.for_actor(
            target_user_id=self.id,
            current_role=self.role,
            new_role=new_role,
            actor_user_id=actor_user_id,
            actor_role=actor_role,
            permissions=permissions,
        )
        RoleAssignmentPolicy().ensure_can_assign(context)

        previous_role = self.role
        object.__setattr__(self, "role", new_role)
        self.rotate_auth_token_version(now)
        self._record_event(
            UserRoleChanged(
                user_id=self.id,
                previous_role=previous_role,
                new_role=new_role,
                actor_user_id=actor_user_id,
                reason=reason,
                occurred_at=self.updated_at,
                auth_token_version=self.auth_token_version,
            )
        )

    def update_profile(
        self,
        *,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
    ) -> None:
        next_first_name = self.first_name if first_name is None else first_name
        next_last_name = self.last_name if last_name is None else last_name
        name = PersonName(next_first_name, next_last_name)
        if name.first_name == self.first_name and name.last_name == self.last_name:
            return
        self.first_name = name.first_name
        self.last_name = name.last_name
        self.updated_at = _system_clock.now()

    def enable_two_factor(self, now: datetime | None = None) -> None:
        from domain.identity.mfa import MfaMethod, MfaPolicy, UserTwoFactorEnabled

        if not MfaPolicy.can_enable_method(MfaMethod.TOTP, already_enabled=self.two_factor_enabled):
            return
        occurred_at = _now_or_system(now)
        object.__setattr__(self, "two_factor_enabled", True)
        self.rotate_auth_token_version(occurred_at)
        self._record_event(
            UserTwoFactorEnabled(
                user_id=self.id,
                occurred_at=self.updated_at,
                auth_token_version=self.auth_token_version,
            )
        )

    def disable_two_factor(self, now: datetime | None = None) -> None:
        from domain.identity.mfa import MfaMethod, MfaPolicy, UserTwoFactorDisabled

        if not MfaPolicy.can_disable_method(MfaMethod.TOTP, enabled=self.two_factor_enabled):
            return
        occurred_at = _now_or_system(now)
        object.__setattr__(self, "two_factor_enabled", False)
        self.rotate_auth_token_version(occurred_at)
        self._record_event(
            UserTwoFactorDisabled(
                user_id=self.id,
                occurred_at=self.updated_at,
                auth_token_version=self.auth_token_version,
            )
        )

    def link_oauth_provider(self, provider: object, now: datetime | None = None) -> None:
        from domain.identity.oauth import UserOAuthLinked

        provider_value = getattr(provider, "value", provider)
        self._record_event(
            UserOAuthLinked(
                user_id=self.id,
                provider=str(provider_value),
                occurred_at=_now_or_system(now),
            )
        )

    def relink_oauth_provider(self, provider: object, now: datetime | None = None) -> None:
        self.link_oauth_provider(provider, now=now)

    def record_login(self, now: datetime | None = None) -> None:
        from domain.identity.authentication import UserLoggedIn

        occurred_at = _now_or_system(now)
        self.last_login = occurred_at
        self._record_event(
            UserLoggedIn(
                user_id=self.id,
                occurred_at=occurred_at,
                auth_token_version=self.auth_token_version,
            )
        )

    def account_status(self) -> AccountStatus:
        return self.status
