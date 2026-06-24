from __future__ import annotations

import logging
from datetime import datetime, timezone

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)


def revoke_user_sessions(user_id, *, reason: str) -> None:
    """Invalidate tokens issued before this moment for a single identity user."""
    if not user_id:
        return
    revoked_at = int(datetime.now(timezone.utc).timestamp())
    ttl = _session_revocation_ttl_seconds()
    cache.set(_session_revocation_key(user_id), revoked_at, timeout=ttl)
    logger.info(
        "identity_user_sessions_revoked",
        extra={
            "user_id": str(user_id),
            "reason": reason,
            "revoked_at": revoked_at,
            "ttl": ttl,
        },
    )


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
