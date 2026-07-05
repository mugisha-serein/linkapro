"""Identity domain entities."""
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

    def rotate_auth_token_version(self) -> None:
        self.auth_token_version += 1
        self.updated_at = utc_now()

    def change_password(self, new_password_hash: PasswordHash) -> None:
        """Update password hash and record change."""
        self.password_hash = new_password_hash
        self.rotate_auth_token_version()

    def mark_verified(self) -> None:
        self.is_verified = True
        self.updated_at = utc_now()

    def deactivate(self) -> None:
        self.is_active = False
        self.rotate_auth_token_version()

    def activate(self) -> None:
        self.is_active = True
        self.updated_at = utc_now()

    def enable_two_factor(self) -> None:
        self.two_factor_enabled = True
        self.updated_at = utc_now()

    def disable_two_factor(self) -> None:
        self.two_factor_enabled = False
        self.rotate_auth_token_version()

    def record_login(self) -> None:
        self.last_login = utc_now()


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
        if isinstance(self.access_token, str):
            self.access_token = OAuthAccessToken(self.access_token)
        if isinstance(self.refresh_token, str):
            self.refresh_token = OAuthRefreshToken(self.refresh_token)

    def update_tokens(
        self,
        *,
        access_token: OAuthAccessToken | str,
        refresh_token: Optional[OAuthRefreshToken | str],
        expires_at: datetime,
    ) -> None:
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

    def is_expired(self) -> bool:
        return utc_now() >= self.expires_at
