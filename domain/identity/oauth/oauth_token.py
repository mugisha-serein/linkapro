"""OAuth token entity."""
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from domain.identity.oauth.oauth_access_token import OAuthAccessToken
from domain.identity.oauth.oauth_linking_policy import OAuthLinkingAction, OAuthLinkingDecision
from domain.identity.oauth.oauth_provider import OAuthProvider
from domain.identity.oauth.oauth_refresh_token import OAuthRefreshToken
from domain.identity.shared.clock import SystemClock


_system_clock = SystemClock()


def _now_or_system(now: datetime | None) -> datetime:
    return now if now is not None else _system_clock.now()


@dataclass
class OAuthToken:
    id: uuid.UUID
    user_id: uuid.UUID
    provider: OAuthProvider
    provider_user_id: str
    access_token: OAuthAccessToken = field(repr=False)
    refresh_token: Optional[OAuthRefreshToken] = field(repr=False)
    expires_at: datetime
    created_at: datetime = field(default_factory=_system_clock.now)

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

    def link_to(
        self,
        account_id: uuid.UUID,
        policy: OAuthLinkingDecision,
        occurred_at: datetime | None = None,
    ) -> None:
        if account_id == self.user_id:
            return
        if (
            policy.action is not OAuthLinkingAction.RELINK_PROVIDER_IDENTITY
            or not policy.provider_identity_owned_by_another_account
        ):
            raise ValueError("OAuth identity reassignment is not authorized")
        if occurred_at is not None and (occurred_at.tzinfo is None or occurred_at.utcoffset() is None):
            raise ValueError("OAuth identity relink time must be timezone-aware")
        self.user_id = account_id

    @staticmethod
    def _validate_expires_at(expires_at: datetime) -> None:
        if expires_at.tzinfo is None or expires_at.utcoffset() is None:
            raise ValueError("OAuth token expiry must be timezone-aware")

    def is_expired(self, now: datetime | None = None) -> bool:
        return _now_or_system(now) >= self.expires_at

    def should_refresh(self, buffer_seconds: int = 60, now: datetime | None = None) -> bool:
        if buffer_seconds < 0:
            raise ValueError("Expiry buffer cannot be negative")
        return _now_or_system(now).timestamp() + buffer_seconds >= self.expires_at.timestamp()
