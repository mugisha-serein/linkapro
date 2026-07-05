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
    parts = [SERVICE_AUTH_VERSION, service, method.upper(), path, timestamp, request_id, payload_hash]
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


def assert_service_request(
    *,
    key: str,
    service: str | None,
    method: str,
    path: str,
    timestamp: str | None,
    request_id: str | None,
    payload_hash: str | None,
    supplied_mac: str | None,
    payload: bytes,
) -> None:
    if service != SERVICE_AUTH_DJANGO_SERVICE:
        raise ServiceAuthError("Unauthorized service.")
    if not request_id:
        raise ServiceAuthError("Request id is required.")
    parsed_timestamp = parse_timestamp(timestamp or "")
    assert_fresh_timestamp(parsed_timestamp)
    expected_payload_hash = payload_digest(payload)
    if payload_hash != expected_payload_hash:
        raise ServiceAuthError("Invalid payload digest.")
    canonical = canonical_service_request(
        service=service,
        method=method,
        path=path,
        timestamp=timestamp or "",
        request_id=request_id,
        payload_hash=expected_payload_hash,
    )
    assert_matching_mac(supplied=supplied_mac or "", expected=service_mac(canonical, key))


def build_service_headers(*, key: str, method: str, path: str, payload: bytes, request_id: str, timestamp: str) -> dict[str, str]:
    payload_hash = payload_digest(payload)
    canonical = canonical_service_request(
        service=SERVICE_AUTH_DJANGO_SERVICE,
        method=method,
        path=path,
        timestamp=timestamp,
        request_id=request_id,
        payload_hash=payload_hash,
    )
    return {
        "X-Service-Name": SERVICE_AUTH_DJANGO_SERVICE,
        "X-Request-Timestamp": timestamp,
        "X-Request-Id": request_id,
        "X-Payload-SHA256": payload_hash,
        "X-Service-MAC": service_mac(canonical, key),
    }
