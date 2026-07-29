"""Command for OAuth login."""

from dataclasses import dataclass, field
from datetime import datetime

from domain.identity.account import AccountRole
from domain.identity.credentials import Email
from domain.identity.oauth import OAuthAccessToken, OAuthProvider, OAuthRefreshToken


@dataclass(frozen=True)
class ProviderIdentity:
    provider: OAuthProvider
    provider_user_id: str
    email: Email
    first_name: str
    last_name: str
    email_verified: bool | None = None


@dataclass(frozen=True)
class GoogleLoginCommand:
    identity: ProviderIdentity
    access_token: OAuthAccessToken = field(repr=False)
    expires_at: datetime
    refresh_token: OAuthRefreshToken | None = field(default=None, repr=False)
    signup_role: AccountRole | None = None


OAuthLoginCommand = GoogleLoginCommand


__all__ = ["GoogleLoginCommand", "OAuthLoginCommand", "ProviderIdentity"]
