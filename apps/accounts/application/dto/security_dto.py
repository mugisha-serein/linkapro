# No Business Logic Here
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


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