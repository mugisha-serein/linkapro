"""Typed token claims and issuance request DTOs."""

from dataclasses import dataclass, field


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
class RefreshTokenClaims:
    raw: str = field(repr=False)
    jti: str
    family: str
    user_id: str | None
    session_id: str | None
    issued_at: int | None
    expires_at: int
    auth_token_version: int | None
    role: str = ""
    scope: str = ""
    step_up: bool = False


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


__all__ = [
    "AccessTokenClaims",
    "IssuedTokenPair",
    "RefreshTokenClaims",
    "RotatedTokenPairRequest",
    "StepUpTokenRequest",
    "TokenBootstrapClaims",
    "TokenClaims",
]
