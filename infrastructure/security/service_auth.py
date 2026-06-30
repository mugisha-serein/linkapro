from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timezone

SERVICE_AUTH_VERSION = "v1"
SERVICE_AUTH_ALLOWED_SKEW_SECONDS = 300
SERVICE_AUTH_DJANGO_SERVICE = "django"


class ServiceAuthError(ValueError):
    pass


def payload_digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def canonical_service_request(
    *,
    service: str,
    method: str,
    path: str,
    timestamp: str,
    request_id: str,
    payload_hash: str,
) -> str:
    parts = [
        SERVICE_AUTH_VERSION,
        service,
        method.upper(),
        path,
        timestamp,
        request_id,
        payload_hash,
    ]
    return "\n".join(parts)


def service_mac(canonical: str, key: str) -> str:
    return hmac.new(key.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256).hexdigest()


def assert_matching_mac(*, supplied: str, expected: str) -> None:
    if not supplied or not hmac.compare_digest(supplied, expected):
        raise ServiceAuthError("Invalid service authentication.")


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_timestamp(value: str) -> datetime:
    if not value:
        raise ServiceAuthError("Service timestamp is required.")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ServiceAuthError("Invalid service timestamp.") from exc
    if parsed.tzinfo is None:
        raise ServiceAuthError("Service timestamp must include timezone.")
    return parsed.astimezone(timezone.utc)


def assert_fresh_timestamp(timestamp: datetime, *, now: datetime | None = None, skew_seconds: int = SERVICE_AUTH_ALLOWED_SKEW_SECONDS) -> None:
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if abs((current - timestamp).total_seconds()) > skew_seconds:
        raise ServiceAuthError("Service timestamp is outside the allowed window.")
