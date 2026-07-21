"""Identity domain entities.

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
from typing import Optional

from domain.shared.utils import utc_now
from .value_objects import (
    Email,
    OAuthAccessToken,
    OAuthProvider,
    OAuthRefreshToken,
    PasswordHash,
    PersonName,
)


class UserRole(str, Enum):
    PLANNER = "planner"
    VENDOR = "vendor"
    ADMIN = "admin"

    @classmethod
    def public_registration_roles(cls) -> tuple["UserRole", ...]:
        return (cls.PLANNER, cls.VENDOR)

    def can_self_register(self) -> bool:
        return self in self.public_registration_roles()


class AccountStatus(str, Enum):
    PENDING_VERIFICATION = "pending_verification"
    ACTIVE = "active"
    DEACTIVATED = "deactivated"
    SUSPENDED = "suspended"


@dataclass
class User:
    id: uuid.UUID
    email: Email
    password_hash: Optional[PasswordHash]
    first_name: str
    last_name: str
    role: UserRole
    two_factor_enabled: bool = False
    auth_token_version: int = 0
    is_active: bool = True
    is_verified: bool = False
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    last_login: Optional[datetime] = None
    _events: list[object] = field(default_factory=list, init=False, repr=False)

    def __post_init__(self) -> None:
        self.role = UserRole(self.role)
        name = PersonName(self.first_name, self.last_name)
        self.first_name = name.first_name
        self.last_name = name.last_name
        if self.auth_token_version < 0:
            raise ValueError("Auth token version cannot be negative")
        self._validate_timezone_aware(self.created_at, "created_at")
        self._validate_timezone_aware(self.updated_at, "updated_at")
        if self.last_login is not None:
            self._validate_timezone_aware(self.last_login, "last_login")

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
    ) -> "User":
        role = UserRole(role)
        if not role.can_self_register():
            raise ValueError("Role cannot self-register")
        return cls(
            id=id,
            email=email,
            password_hash=password_hash,
            first_name=first_name,
            last_name=last_name,
            role=role,
            is_verified=is_verified,
        )

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
            is_active=is_active,
            is_verified=is_verified,
            created_at=created_at,
            updated_at=updated_at,
            last_login=last_login,
        )

    def _record_event(self, event: object) -> None:
        self._events.append(event)

    def pull_events(self) -> list[object]:
        events = list(self._events)
        self._events.clear()
        return events

    def rotate_auth_token_version(self) -> None:
        self.auth_token_version += 1
        self.updated_at = utc_now()

    def change_password(self, new_password_hash: PasswordHash) -> None:
        """Update password hash and record change."""
        from .events import UserPasswordChanged

        self.password_hash = new_password_hash
        self.rotate_auth_token_version()
        self._record_event(
            UserPasswordChanged(
                user_id=self.id,
                occurred_at=self.updated_at,
                auth_token_version=self.auth_token_version,
            )
        )

    def mark_verified(self) -> None:
        from .events import UserVerified

        if self.is_verified:
            return
        self.is_verified = True
        self.updated_at = utc_now()
        self._record_event(
            UserVerified(
                user_id=self.id,
                occurred_at=self.updated_at,
                auth_token_version=self.auth_token_version,
            )
        )

    def deactivate(self) -> None:
        from .events import UserDeactivated

        if not self.is_active:
            return
        self.is_active = False
        self.rotate_auth_token_version()
        self._record_event(
            UserDeactivated(
                user_id=self.id,
                occurred_at=self.updated_at,
                auth_token_version=self.auth_token_version,
            )
        )

    def activate(self) -> None:
        from .events import UserActivated

        if self.is_active:
            return
        self.is_active = True
        self.updated_at = utc_now()
        self._record_event(
            UserActivated(
                user_id=self.id,
                occurred_at=self.updated_at,
                auth_token_version=self.auth_token_version,
            )
        )

    def enable_two_factor(self) -> None:
        from .events import UserTwoFactorEnabled

        if self.two_factor_enabled:
            return
        self.two_factor_enabled = True
        self.rotate_auth_token_version()
        self._record_event(
            UserTwoFactorEnabled(
                user_id=self.id,
                occurred_at=self.updated_at,
                auth_token_version=self.auth_token_version,
            )
        )

    def disable_two_factor(self) -> None:
        from .events import UserTwoFactorDisabled

        if not self.two_factor_enabled:
            return
        self.two_factor_enabled = False
        self.rotate_auth_token_version()
        self._record_event(
            UserTwoFactorDisabled(
                user_id=self.id,
                occurred_at=self.updated_at,
                auth_token_version=self.auth_token_version,
            )
        )

    def record_login(self) -> None:
        self.last_login = utc_now()

    def account_status(self) -> AccountStatus:
        if not self.is_active:
            return AccountStatus.DEACTIVATED
        if not self.is_verified:
            return AccountStatus.PENDING_VERIFICATION
        return AccountStatus.ACTIVE


@dataclass
class OAuthToken:
    id: uuid.UUID
    user_id: uuid.UUID
    provider: OAuthProvider
    provider_user_id: str
    access_token: OAuthAccessToken = field(repr=False)
    refresh_token: Optional[OAuthRefreshToken] = field(repr=False)
    expires_at: datetime
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        if not self.provider_user_id.strip():
            raise ValueError("Provider user ID cannot be empty")
        if isinstance(self.access_token, str):
            self.access_token = OAuthAccessToken(self.access_token)
        if isinstance(self.refresh_token, str):
            self.refresh_token = OAuthRefreshToken(self.refresh_token)
        self._validate_expires_at(self.expires_at)

    def update_tokens(
        self,
        *,
        access_token: OAuthAccessToken | str,
        refresh_token: Optional[OAuthRefreshToken | str],
        expires_at: datetime,
    ) -> None:
        self._validate_expires_at(expires_at)
        self.access_token = (
            access_token
            if isinstance(access_token, OAuthAccessToken)
            else OAuthAccessToken(access_token)
        )
        self.refresh_token = (
            refresh_token
            if refresh_token is None or isinstance(refresh_token, OAuthRefreshToken)
            else OAuthRefreshToken(refresh_token)
        )
        self.expires_at = expires_at

    @staticmethod
    def _validate_expires_at(expires_at: datetime) -> None:
        if expires_at.tzinfo is None or expires_at.utcoffset() is None:
            raise ValueError("OAuth token expiry must be timezone-aware")

    def is_expired(self) -> bool:
        return utc_now() >= self.expires_at

    def should_refresh(self, buffer_seconds: int = 60) -> bool:
        if buffer_seconds < 0:
            raise ValueError("Expiry buffer cannot be negative")
        return utc_now().timestamp() + buffer_seconds >= self.expires_at.timestamp()
