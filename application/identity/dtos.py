"""Data Transfer Objects for identity module."""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
import uuid


@dataclass(frozen=True)
class UserDTO:
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
    is_authenticated: Optional[bool] = None
    onboarding_complete: Optional[bool] = None


@dataclass(frozen=True)
class SessionBootstrapDTO:
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
            "created_at": self.created_at,
            "last_login": self.last_login,
            "is_authenticated": self.is_authenticated,
            "onboarding_complete": self.onboarding_complete,
        }

    @classmethod
    def from_user(cls, user) -> "SessionBootstrapDTO":
        has_password = bool(user.password_hash)
        display_name = f"{user.first_name} {user.last_name}".strip()
        if not display_name:
            display_name = user.first_name or user.last_name or user.email.value
        return cls(
            id=user.id,
            email=str(user.email),
            role=user.role.value,
            first_name=user.first_name,
            last_name=user.last_name,
            display_name=display_name,
            avatar=None,
            is_active=user.is_active,
            is_verified=user.is_verified,
            has_password=has_password,
            requires_password_setup=not has_password,
            two_factor_enabled=user.two_factor_enabled,
            created_at=user.created_at.isoformat() if user.created_at else None,
            last_login=user.last_login.isoformat() if user.last_login else None,
            onboarding_complete=user.is_verified and has_password,
        )


@dataclass(frozen=True)
class AuthenticationResultDTO:
    user: UserDTO
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"

@dataclass(frozen=True)
class TwoFactorSetupDTO:
    secret: str
    provisioning_uri: str
    qr_code_base64: Optional[str] = None   # can be generated on client side

@dataclass(frozen=True)
class TwoFactorChallengeDTO:
    temp_token: str
    expires_in: int   # seconds
