"""Commands for identity write operations."""
from dataclasses import dataclass
from typing import Optional
import uuid

from domain.identity.value_objects import Email, PlainPassword, OAuthProvider


@dataclass(frozen=True)
class RegisterUserCommand:
    email: Email
    plain_password: PlainPassword
    first_name: str
    last_name: str
    role: str  # Will be validated as UserRole


@dataclass(frozen=True)
class LoginUserCommand:
    email: Email
    plain_password: PlainPassword


@dataclass(frozen=True)
class OAuthLoginCommand:
    provider: OAuthProvider
    provider_user_id: str
    email: Email
    first_name: str
    last_name: str
    access_token: str
    refresh_token: Optional[str]
    expires_in: int  # seconds


@dataclass(frozen=True)
class ChangePasswordCommand:
    user_id: uuid.UUID
    old_plain_password: PlainPassword
    new_plain_password: PlainPassword


@dataclass(frozen=True)
class RequestPasswordResetCommand:
    email: Email


@dataclass(frozen=True)
class ResetPasswordCommand:
    reset_token: str
    new_plain_password: PlainPassword


@dataclass(frozen=True)
class VerifyEmailCommand:
    verification_token: str


@dataclass(frozen=True)
class UpdateProfileCommand:
    user_id: uuid.UUID
    first_name: Optional[str] = None
    last_name: Optional[str] = None


@dataclass(frozen=True)
class DeactivateUserCommand:
    user_id: uuid.UUID

@dataclass(frozen=True)
class EnableTwoFactorCommand:
    user_id: uuid.UUID

@dataclass(frozen=True)
class VerifyTwoFactorSetupCommand:
    user_id: uuid.UUID
    token: str   # TOTP code from authenticator app

@dataclass(frozen=True)
class LoginTwoFactorCommand:
    temp_token: str   # temporary token issued after password verification
    token: str        # TOTP code