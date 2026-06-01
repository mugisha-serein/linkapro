"""Signed OAuth state parameter for Google signup role selection."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Optional

from django.conf import settings

ALLOWED_OAUTH_SIGNUP_ROLES = frozenset({"planner", "vendor"})
_STATE_TTL_SECONDS = 600


def _signing_key() -> bytes:
    return str(settings.SECRET_KEY).encode("utf-8")


def build_oauth_state(signup_role: str) -> str:
    role = (signup_role or "").strip().lower()
    if role not in ALLOWED_OAUTH_SIGNUP_ROLES:
        raise ValueError("Invalid OAuth signup role")

    payload = {
        "role": role,
        "exp": int(time.time()) + _STATE_TTL_SECONDS,
        "nonce": secrets.token_urlsafe(16),
    }
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    payload_b64 = payload_b64.decode("utf-8").rstrip("=")
    signature = hmac.new(_signing_key(), payload_b64.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload_b64}.{signature}"


def parse_oauth_state(state: str | None) -> Optional[str]:
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

    role = (payload.get("role") or "").strip().lower()
    exp = payload.get("exp")
    if role not in ALLOWED_OAUTH_SIGNUP_ROLES:
        return None
    if not isinstance(exp, int) or exp < int(time.time()):
        return None
    return role
