from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from django.conf import settings
from django.core.cache import cache
from django.db.models import F

logger = logging.getLogger(__name__)

AUTH_TOKEN_VERSION_CLAIM = "auth_token_version"


@dataclass(frozen=True)
class UserTokenState:
    user_id: str
    auth_token_version: int
    is_active: bool


def revoke_user_sessions(user_id, *, reason: str) -> None:
    """Invalidate tokens issued before this moment for a single identity user."""
    if not user_id:
        return
    revoked_at = int(datetime.now(timezone.utc).timestamp())
    ttl = _session_revocation_ttl_seconds()
    new_version = bump_user_auth_token_version(user_id)
    cache.set(_session_revocation_key(user_id), revoked_at, timeout=ttl)
    logger.info(
        "identity_user_sessions_revoked",
        extra={
            "user_id": str(user_id),
            "reason": reason,
            "revoked_at": revoked_at,
            "auth_token_version": new_version,
            "ttl": ttl,
        },
    )


def bump_user_auth_token_version(user_id) -> int | None:
    if not user_id:
        return None
    from django_app.identity.models import User

    updated = User.objects.filter(id=user_id).update(auth_token_version=F("auth_token_version") + 1)
    if not updated:
        logger.warning("identity_auth_token_version_bump_skipped", extra={"user_id": str(user_id)})
        return None
    return get_user_auth_token_version(user_id)


def get_user_auth_token_version(user_id) -> int | None:
    state = get_user_token_state(user_id)
    return state.auth_token_version if state else None


def get_user_token_state(user_id) -> UserTokenState | None:
    if not user_id:
        return None
    from django_app.identity.models import User

    row = (
        User.objects.filter(id=user_id)
        .values("id", "auth_token_version", "is_active")
        .first()
    )
    if not row:
        return None
    return UserTokenState(
        user_id=str(row["id"]),
        auth_token_version=int(row["auth_token_version"]),
        is_active=bool(row["is_active"]),
    )


def token_version_matches_user(user_id, token_version) -> bool:
    state = get_user_token_state(user_id)
    if state is None:
        return False
    return _coerce_int(token_version) == state.auth_token_version


def token_version_matches_active_user(user_id, token_version) -> bool:
    state = get_user_token_state(user_id)
    if state is None or not state.is_active:
        return False
    return _coerce_int(token_version) == state.auth_token_version


def is_token_revoked_for_user(user_id, issued_at) -> bool:
    """Return True when a token was issued before the user's latest revocation cutoff."""
    if not user_id or issued_at is None:
        return False

    revoked_after = cache.get(_session_revocation_key(user_id))
    if revoked_after is None:
        return False

    issued_at_timestamp = _coerce_timestamp(issued_at)
    if issued_at_timestamp is None:
        return True

    return issued_at_timestamp < int(revoked_after)


def _session_revocation_key(user_id) -> str:
    return f"identity:user_sessions_revoked_after:{user_id}"


def _session_revocation_ttl_seconds() -> int:
    refresh_lifetime = settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"]
    return max(int(refresh_lifetime.total_seconds()), 1)


def _coerce_timestamp(value) -> int | None:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return int(value.timestamp())
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _coerce_int(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
