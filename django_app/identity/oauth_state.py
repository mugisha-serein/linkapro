"""Signed OAuth state for role-first Google sign-in."""

from __future__ import annotations

import json
import secrets

from django.core import signing

OAUTH_STATE_SALT = "linkapro.google-oauth-state"
OAUTH_STATE_MAX_AGE_SECONDS = 600
ALLOWED_OAUTH_ROLES = frozenset({"planner", "vendor"})


class OAuthStateError(ValueError):
    """Invalid or expired OAuth state."""


def build_oauth_state(role: str) -> str:
    normalized = (role or "").strip().lower()
    if normalized not in ALLOWED_OAUTH_ROLES:
        raise OAuthStateError("Invalid role for Google sign-in")

    payload = json.dumps(
        {"role": normalized, "nonce": secrets.token_urlsafe(16)},
        separators=(",", ":"),
    )
    return signing.TimestampSigner(salt=OAUTH_STATE_SALT).sign(payload)


def parse_oauth_state(state: str | None) -> str:
    if not state:
        raise OAuthStateError("Missing OAuth state")

    try:
        raw = signing.TimestampSigner(salt=OAUTH_STATE_SALT).unsign(
            state,
            max_age=OAUTH_STATE_MAX_AGE_SECONDS,
        )
    except signing.SignatureExpired as exc:
        raise OAuthStateError("OAuth session expired. Please try again.") from exc
    except signing.BadSignature as exc:
        raise OAuthStateError("Invalid OAuth state") from exc

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise OAuthStateError("Invalid OAuth state payload") from exc

    role = (data.get("role") or "").strip().lower()
    if role not in ALLOWED_OAUTH_ROLES:
        raise OAuthStateError("Invalid role in OAuth state")

    return role
