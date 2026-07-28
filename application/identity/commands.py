"""Commands for identity write operations."""
from dataclasses import dataclass, field
from typing import Optional
import uuid

from domain.identity.account import AccountRole
from domain.identity.credentials import Email, PlainPassword
from domain.identity.oauth import OAuthAccessToken, OAuthProvider, OAuthRefreshToken
from domain.identity.verification import VerificationCode


@dataclass(frozen=True)
class RegisterUserCommand:
    email: Email
    plain_password: PlainPassword = field(repr=False)
    first_name: str
    last_name: str
    role: AccountRole


@dataclass(frozen=True)
class OAuthLoginCommand:
    provider: OAuthProvider
    provider_user_id: str
    access_token: OAuthAccessToken = field(repr=False)
    refresh_token: OAuthRefreshToken | None = field(default=None, repr=False)
    signup_role: AccountRole | None = None


@dataclass(frozen=True)
class LoginUserCommand:
    email: Email
    plain_password: PlainPassword = field(repr=False)


@dataclass(frozen=True)
class VerifyEmailCommand:
    verification_token: str = field(repr=False)


@dataclass(frozen=True)
class UpdateProfileCommand:
    user_id: uuid.UUID
    first_name: Optional[str] = None
    last_name: Optional[str] = None


@dataclass(frozen=True)
class DeactivateUserCommand:
    user_id: uuid.UUID
    actor_id: Optional[uuid.UUID] = None
    reason: Optional[str] = None


@dataclass(frozen=True)
class AssignRoleCommand:
    actor_id: uuid.UUID
    target_user_id: uuid.UUID
    new_role: str
    reason: Optional[str] = None


@dataclass(frozen=True)
class SuspendAccountCommand:
    actor_id: uuid.UUID
    target_user_id: uuid.UUID
    reason: str


@dataclass(frozen=True)
class ReactivateAccountCommand:
    actor_id: uuid.UUID
    target_user_id: uuid.UUID
    reason: Optional[str] = None


@dataclass(frozen=True)
class UnlockAccountCommand:
    actor_id: uuid.UUID
    target_user_id: uuid.UUID
    reason: Optional[str] = None


@dataclass(frozen=True)
class EnableTwoFactorCommand:
    user_id: uuid.UUID

@dataclass(frozen=True)
class VerifyTwoFactorSetupCommand:
    user_id: uuid.UUID
    token: VerificationCode = field(repr=False)  # TOTP code from authenticator app

@dataclass(frozen=True)
class DisableMfaCommand:
    user_id: uuid.UUID


@dataclass(frozen=True)
class ChangePasswordCommand:
    user_id: uuid.UUID
    current_password: PlainPassword = field(repr=False)
    new_password: PlainPassword = field(repr=False)


@dataclass(frozen=True)
class SetupPasswordCommand:
    user_id: uuid.UUID
    plain_password: PlainPassword = field(repr=False)


@dataclass(frozen=True)
class LoginTwoFactorCommand:
    temp_token: str = field(repr=False)  # temporary token issued after password verification
    token: VerificationCode = field(repr=False)  # TOTP code


@dataclass(frozen=True)
class ResetPasswordCommand:
    token: str = field(repr=False)
    new_password: str = field(repr=False)
    client_ip: str
    user_agent: str
