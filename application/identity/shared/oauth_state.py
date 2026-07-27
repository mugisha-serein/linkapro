"""Browser-bound signed OAuth state parameter for Google signup role selection."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass
from typing import Optional

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured

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


def _signing_key() -> bytes:
    return str(settings.SECRET_KEY).encode("utf-8")


def issue_oauth_state(signup_role: str) -> OAuthStateChallenge:
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
    state = _encode_signed_payload(payload)
    cache.set(_cache_key(nonce), {"role": role, "exp": expires_at}, timeout=_STATE_TTL_SECONDS)
    return OAuthStateChallenge(state=state, nonce=nonce)


def consume_oauth_state(state: str | None, cookie_nonce: str | None) -> Optional[OAuthStateResult]:
    if not state or not cookie_nonce:
        return None

    payload = _decode_signed_payload(state)
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

    cached = cache.get(_cache_key(nonce))
    if not cached:
        return None
    cache.delete(_cache_key(nonce))
    if cached.get("role") != role:
        return None
    return OAuthStateResult(role=role, nonce=nonce)


def set_oauth_state_cookie(response, challenge: OAuthStateChallenge) -> None:
    response.set_cookie(
        OAUTH_STATE_COOKIE_NAME,
        challenge.nonce,
        max_age=challenge.max_age,
        httponly=True,
        secure=_oauth_state_cookie_secure(),
        samesite=_oauth_state_cookie_samesite(),
        path=_oauth_state_cookie_path(),
        domain=_oauth_state_cookie_domain(),
    )


def clear_oauth_state_cookie(response) -> None:
    response.set_cookie(
        OAUTH_STATE_COOKIE_NAME,
        "",
        max_age=0,
        expires="Thu, 01 Jan 1970 00:00:00 GMT",
        httponly=True,
        secure=_oauth_state_cookie_secure(),
        samesite=_oauth_state_cookie_samesite(),
        path=_oauth_state_cookie_path(),
        domain=_oauth_state_cookie_domain(),
    )


def _encode_signed_payload(payload: dict) -> str:
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    payload_b64 = payload_b64.decode("utf-8").rstrip("=")
    signature = hmac.new(_signing_key(), payload_b64.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload_b64}.{signature}"


def _decode_signed_payload(state: str | None) -> Optional[dict]:
    if not state or "." not in state:
        return None
    payload_b64, signature = state.rsplit(".", 1)
    expected = hmac.new(_signing_key(), payload_b64.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        return None

    padding = "=" * (-len(payload_b64) % 4)
    try:
        payload = json.loads(base64.urlsafe_b64decode(payload_b64 + padding).decode("utf-8"))
    except (json.JSONDecodeError, ValueError, UnicodeDecodeError):
        return None
    return payload


def _cache_key(nonce: str) -> str:
    nonce_hash = hmac.new(_signing_key(), nonce.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"oauth_state_nonce:{nonce_hash}"


def _oauth_state_cookie_domain() -> str | None:
    cookie_domain = str(getattr(settings, "OAUTH_STATE_COOKIE_DOMAIN", "") or "").strip()
    return cookie_domain or None


def _oauth_state_cookie_path() -> str:
    return str(getattr(settings, "OAUTH_STATE_COOKIE_PATH", "/") or "/").strip() or "/"


def _oauth_state_cookie_samesite() -> str:
    configured = str(getattr(settings, "OAUTH_STATE_COOKIE_SAMESITE", "") or "").strip()
    if configured:
        normalized = configured.capitalize()
        if normalized not in {"Lax", "Strict", "None"}:
            raise ImproperlyConfigured("OAUTH_STATE_COOKIE_SAMESITE must be one of Lax, Strict, or None")
        return normalized
    return "Lax"


def _oauth_state_cookie_secure() -> bool:
    configured = getattr(settings, "OAUTH_STATE_COOKIE_SECURE", None)
    secure = not settings.DEBUG if configured is None else bool(configured)
    if not settings.DEBUG and not secure:
        raise ImproperlyConfigured("OAUTH_STATE_COOKIE_SECURE must be enabled in production")
    if _oauth_state_cookie_samesite() == "None" and not secure:
        raise ImproperlyConfigured("SameSite=None OAuth state cookies require Secure=True")
    return secure
