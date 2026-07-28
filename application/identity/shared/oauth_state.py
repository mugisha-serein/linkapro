"""Browser-bound signed OAuth state parameter for Google signup role selection."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass
from typing import Any, Optional, Protocol


ALLOWED_OAUTH_SIGNUP_ROLES = frozenset({"planner", "vendor"})
OAUTH_STATE_COOKIE_NAME = "oauth_state_nonce"
_STATE_TTL_SECONDS = 600


@dataclass(frozen=True)
class OAuthStateChallenge:
    state: str
    nonce: str
    max_age: int = _STATE_TTL_SECONDS


@dataclass(frozen=True)
class OAuthStateResult:
    role: str
    nonce: str


class OAuthStateCache(Protocol):
    def set(self, key: str, value: Any, timeout: int) -> None:
        ...

    def get(self, key: str) -> Any | None:
        ...

    def delete(self, key: str) -> None:
        ...


def _signing_key(signing_key: str | bytes) -> bytes:
    if isinstance(signing_key, bytes):
        return signing_key
    return str(signing_key).encode("utf-8")


def issue_oauth_state(
    signup_role: str,
    *,
    signing_key: str | bytes,
    state_cache: OAuthStateCache,
) -> OAuthStateChallenge:
    role = (signup_role or "").strip().lower()
    if role not in ALLOWED_OAUTH_SIGNUP_ROLES:
        raise ValueError("Invalid OAuth signup role")

    nonce = secrets.token_urlsafe(32)
    expires_at = int(time.time()) + _STATE_TTL_SECONDS
    payload = {
        "role": role,
        "exp": expires_at,
        "nonce": nonce,
    }
    state = _encode_signed_payload(payload, signing_key=signing_key)
    state_cache.set(_cache_key(nonce, signing_key=signing_key), {"role": role, "exp": expires_at}, timeout=_STATE_TTL_SECONDS)
    return OAuthStateChallenge(state=state, nonce=nonce)


def consume_oauth_state(
    state: str | None,
    cookie_nonce: str | None,
    *,
    signing_key: str | bytes,
    state_cache: OAuthStateCache,
) -> Optional[OAuthStateResult]:
    if not state or not cookie_nonce:
        return None

    payload = _decode_signed_payload(state, signing_key=signing_key)
    if not payload:
        return None

    role = (payload.get("role") or "").strip().lower()
    nonce = (payload.get("nonce") or "").strip()
    exp = payload.get("exp")
    if role not in ALLOWED_OAUTH_SIGNUP_ROLES:
        return None
    if not isinstance(exp, int) or exp < int(time.time()):
        return None
    if not nonce or not hmac.compare_digest(nonce, str(cookie_nonce)):
        return None

    cached = state_cache.get(_cache_key(nonce, signing_key=signing_key))
    if not cached:
        return None
    state_cache.delete(_cache_key(nonce, signing_key=signing_key))
    if cached.get("role") != role:
        return None
    return OAuthStateResult(role=role, nonce=nonce)


def set_oauth_state_cookie(
    response,
    challenge: OAuthStateChallenge,
    *,
    secure: bool,
    samesite: str,
    path: str = "/",
    domain: str | None = None,
) -> None:
    response.set_cookie(
        OAUTH_STATE_COOKIE_NAME,
        challenge.nonce,
        max_age=challenge.max_age,
        httponly=True,
        secure=secure,
        samesite=samesite,
        path=path,
        domain=domain,
    )


def clear_oauth_state_cookie(
    response,
    *,
    secure: bool,
    samesite: str,
    path: str = "/",
    domain: str | None = None,
) -> None:
    response.set_cookie(
        OAUTH_STATE_COOKIE_NAME,
        "",
        max_age=0,
        expires="Thu, 01 Jan 1970 00:00:00 GMT",
        httponly=True,
        secure=secure,
        samesite=samesite,
        path=path,
        domain=domain,
    )


def _encode_signed_payload(payload: dict, *, signing_key: str | bytes) -> str:
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    payload_b64 = payload_b64.decode("utf-8").rstrip("=")
    signature = hmac.new(_signing_key(signing_key), payload_b64.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload_b64}.{signature}"


def _decode_signed_payload(state: str | None, *, signing_key: str | bytes) -> Optional[dict]:
    if not state or "." not in state:
        return None
    payload_b64, signature = state.rsplit(".", 1)
    expected = hmac.new(_signing_key(signing_key), payload_b64.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        return None

    padding = "=" * (-len(payload_b64) % 4)
    try:
        payload = json.loads(base64.urlsafe_b64decode(payload_b64 + padding).decode("utf-8"))
    except (json.JSONDecodeError, ValueError, UnicodeDecodeError):
        return None
    return payload


def _cache_key(nonce: str, *, signing_key: str | bytes) -> str:
    nonce_hash = hmac.new(_signing_key(signing_key), nonce.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"oauth_state_nonce:{nonce_hash}"
