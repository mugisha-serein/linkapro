"""Typed token claims and issuance request DTOs."""

from dataclasses import dataclass, field
from datetime import datetime
import uuid

from domain.identity.sessions import RefreshTokenSnapshot, TokenFamily


@dataclass(frozen=True)
class TokenBootstrapClaims:
    values: dict


@dataclass(frozen=True)
class TokenClaims:
    user_id: str
    role: str | None = None
    family: str | None = None
    session_id: str | None = None
    auth_token_version: int | None = None
    scope: str = ""
    step_up: bool = False


@dataclass(frozen=True)
class RefreshTokenClaims(RefreshTokenSnapshot):
    raw: str = field(repr=False)
    expires_at: int
    role: str = ""
    scope: str = ""
    step_up: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.family, TokenFamily):
            object.__setattr__(self, "family", TokenFamily(self.family))


@dataclass(frozen=True)
class AccessTokenClaims:
    user_id: str
    family: str
    session_id: str | None
    scope: str = ""
    bootstrap_claims: TokenBootstrapClaims | None = None


@dataclass(frozen=True)
class RotatedTokenPairRequest:
    claims: RefreshTokenClaims
    access_jti: str
    refresh_jti: str
    bootstrap_claims: TokenBootstrapClaims


@dataclass(frozen=True)
class IssuedTokenPair:
    access_token: str = field(repr=False)
    refresh_token: str = field(repr=False)
    bootstrap_claims: TokenBootstrapClaims


@dataclass(frozen=True)
class StepUpTokenRequest:
    claims: AccessTokenClaims
    jti: str


@dataclass(frozen=True)
class MfaLoginGrant:
    grant_id: str
    account_id: uuid.UUID
    expires_at: datetime
    challenge_id: uuid.UUID

    def remaining_ttl_seconds(self, *, now: datetime) -> int:
        return max(int((self.expires_at - now).total_seconds()), 1)


__all__ = [
    "AccessTokenClaims",
    "IssuedTokenPair",
    "RefreshTokenClaims",
    "RotatedTokenPairRequest",
    "StepUpTokenRequest",
    "TokenBootstrapClaims",
    "TokenClaims",
    "MfaLoginGrant",
]
