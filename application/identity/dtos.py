"""Data Transfer Objects for identity module."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import uuid


@dataclass(frozen=True)
class AccountDTO:
    id: uuid.UUID
    email: str
    first_name: str
    last_name: str
    role: str
    is_active: bool
    is_verified: bool
    created_at: datetime
    last_login: Optional[datetime]
    display_name: Optional[str] = None
    avatar: Optional[str] = None
    has_password: Optional[bool] = None
    requires_password_setup: Optional[bool] = None
    two_factor_enabled: Optional[bool] = None
    auth_token_version: int = 0
    is_authenticated: Optional[bool] = None
    onboarding_complete: Optional[bool] = None


@dataclass(frozen=True)
class AuthenticationResult:
    status: object
    user: Optional[object] = None
    access_token: Optional[str] = field(default=None, repr=False)
    refresh_token: Optional[str] = field(default=None, repr=False)
    temp_token: Optional[str] = field(default=None, repr=False)
    bootstrap_user: Optional[dict] = None


@dataclass(frozen=True)
class SessionBootstrap:
    id: uuid.UUID
    email: str
    role: str
    first_name: str
    last_name: str
    display_name: str
    avatar: Optional[str]
    is_active: bool
    is_verified: bool
    has_password: bool
    requires_password_setup: bool
    two_factor_enabled: bool
    auth_token_version: int = 0
    created_at: Optional[str] = None
    last_login: Optional[str] = None
    is_authenticated: bool = True
    onboarding_complete: bool = True

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "email": self.email,
            "role": self.role,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "display_name": self.display_name,
            "avatar": self.avatar,
            "is_active": self.is_active,
            "is_verified": self.is_verified,
            "has_password": self.has_password,
            "requires_password_setup": self.requires_password_setup,
            "two_factor_enabled": self.two_factor_enabled,
            "auth_token_version": self.auth_token_version,
            "created_at": self.created_at,
            "last_login": self.last_login,
            "is_authenticated": self.is_authenticated,
            "onboarding_complete": self.onboarding_complete,
        }


@dataclass(frozen=True)
class AuthenticationResultDTO:
    user: AccountDTO
    access_token: str = field(repr=False)
    refresh_token: str = field(repr=False)
    token_type: str = "Bearer"


UserDTO = AccountDTO
SessionBootstrapDTO = SessionBootstrap

@dataclass(frozen=True)
class TwoFactorSetupDTO:
    enrollment_id: str
    secret: str = field(repr=False)
    provisioning_uri: str

@dataclass(frozen=True)
class TwoFactorChallengeDTO:
    temp_token: str = field(repr=False)
    expires_in: int   # seconds
