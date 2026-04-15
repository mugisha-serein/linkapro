# No Business Logic Here
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID
from typing import Any


@dataclass(slots=True)
class LoginCommand:
    email: str
    password: str
    ip_address: str
    user_agent: str
    fingerprint_hash: str
    country_code: str | None = None
    device_type: str | None = None
    browser: str | None = None
    os: str | None = None
    timezone: str | None = None
    language: str | None = None
    canvas_hash: str | None = None
    webgl_hash: str | None = None
    ip_cidr: str | None = None


@dataclass(slots=True)
class CredentialVerificationResult:
    authenticated: bool
    status: str = "FAILED"
    failure_reason: str | None = None


@dataclass(slots=True)
class IssuedLoginTokens:
    access_token: str
    refresh_token: str
    refresh_token_jti: str
    refresh_token_hash: str
    session_key: str
    family_id: UUID
    issued_at: datetime
    access_expires_at: datetime
    refresh_expires_at: datetime


@dataclass(slots=True)
class LoginResult:
    authenticated: bool
    status: str
    failure_reason: str | None = None
    user: Any | None = None
    device: Any | None = None
    session: Any | None = None
    refresh_token: Any | None = None
    activity: Any | None = None
    tokens: IssuedLoginTokens | None = None


@dataclass(slots=True)
class LogoutCommand:
    session_key: str
    ip_address: str
    user_agent: str
    country_code: str | None = None


@dataclass(slots=True)
class LogoutResult:
    success: bool
    status: str
    failure_reason: str | None = None
    user: Any | None = None
    session: Any | None = None
    activity: Any | None = None


@dataclass(slots=True)
class RefreshTokenCommand:
    refresh_token: str
    ip_address: str
    user_agent: str
    country_code: str | None = None


@dataclass(slots=True)
class RefreshTokenResult:
    success: bool
    status: str
    failure_reason: str | None = None
    user: Any | None = None
    session: Any | None = None
    refresh_token: Any | None = None
    activity: Any | None = None
    tokens: IssuedLoginTokens | None = None


@dataclass(slots=True)
class RegisterUserCommand:
    email: str
    password: str
    role: str
    ip_address: str
    user_agent: str
    country_code: str | None = None


@dataclass(slots=True)
class RegisterUserResult:
    success: bool
    status: str
    failure_reason: str | None = None
    user: Any | None = None
    activity: Any | None = None


@dataclass(slots=True)
class RevokeSessionCommand:
    session_id: str
    reason: str
    ip_address: str
    user_agent: str
    country_code: str | None = None


@dataclass(slots=True)
class RevokeSessionResult:
    success: bool
    status: str
    failure_reason: str | None = None
    session: Any | None = None
    activity: Any | None = None


@dataclass(slots=True)
class EvaluateLoginSecurityCommand:
    user_id: str
    ip_address: str
    user_agent: str
    fingerprint_hash: str
    country_code: str | None = None
    device_type: str | None = None
    browser: str | None = None
    os: str | None = None
    timezone: str | None = None
    language: str | None = None


@dataclass(slots=True)
class EvaluateLoginSecurityResult:
    risk_score: int
    risk_level: str
    flags: list[str]
    recommendations: list[str]
    allow_login: bool


@dataclass(slots=True)
class DetectAnomalyCommand:
    user_id: str
    activity_type: str
    ip_address: str
    user_agent: str
    session_key: str | None = None
    device_fingerprint: str | None = None


@dataclass(slots=True)
class DetectAnomalyResult:
    is_anomalous: bool
    anomaly_score: float
    anomaly_type: str | None = None
    confidence: float = 0.0
    details: dict[str, Any] | None = None


@dataclass(slots=True)
class GetProfileCommand:
    user_id: str


@dataclass(slots=True)
class GetProfileResult:
    success: bool
    user: Any | None = None
    failure_reason: str | None = None


@dataclass(slots=True)
class UpdateProfileCommand:
    user_id: str
    email: str | None = None
    role: str | None = None
    is_active: bool | None = None


@dataclass(slots=True)
class UpdateProfileResult:
    success: bool
    user: Any | None = None
    failure_reason: str | None = None
    changes_made: list[str] | None = None
