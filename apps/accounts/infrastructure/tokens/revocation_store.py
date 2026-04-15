from __future__ import annotations

from datetime import datetime
from uuid import UUID

from django.utils import timezone

from apps.accounts.infrastructure.cache import CacheService


class RevocationStore:
    """
    Cache-based revocation registry.

    Responsibility:
    - store revocation markers
    - enforce deterministic lookup semantics
    """

    TOKEN_PREFIX = "accounts:jwt:revoked:token:"
    USER_PREFIX = "accounts:jwt:revoked:user:"
    SESSION_PREFIX = "accounts:jwt:revoked:session:"

    def __init__(self, cache_service: CacheService | None = None) -> None:
        self.cache = cache_service or CacheService()

    # -------------------------
    # TOKEN REVOCATION
    # -------------------------
    def set_token_revocation(
        self,
        jti: str,
        expires_at: datetime,
        payload: dict | None = None,
    ) -> None:
        self.cache.set(
            self._token_key(jti),
            self._normalize_payload(payload),
            timeout=self._safe_ttl(expires_at),
        )

    def get_token_revocation(self, jti: str):
        return self.cache.get(self._token_key(jti))

    def delete_token_revocation(self, jti: str) -> None:
        self.cache.delete(self._token_key(jti))

    # -------------------------
    # USER REVOCATION
    # -------------------------
    def set_user_revocation(
        self,
        user_id: UUID | str,
        expires_at: datetime,
        payload: dict | None = None,
    ) -> None:
        self.cache.set(
            self._user_key(user_id),
            self._normalize_payload(payload),
            timeout=self._safe_ttl(expires_at),
        )

    def get_user_revocation(self, user_id: UUID | str):
        return self.cache.get(self._user_key(user_id))

    def delete_user_revocation(self, user_id: UUID | str) -> None:
        self.cache.delete(self._user_key(user_id))

    # -------------------------
    # SESSION REVOCATION
    # -------------------------
    def set_session_revocation(
        self,
        session_key: str,
        expires_at: datetime,
        payload: dict | None = None,
    ) -> None:
        self.cache.set(
            self._session_key(session_key),
            self._normalize_payload(payload),
            timeout=self._safe_ttl(expires_at),
        )

    def get_session_revocation(self, session_key: str):
        return self.cache.get(self._session_key(session_key))

    def delete_session_revocation(self, session_key: str) -> None:
        self.cache.delete(self._session_key(session_key))

    # -------------------------
    # INTERNAL KEY BUILDERS
    # -------------------------
    def _token_key(self, jti: str) -> str:
        return f"{self.TOKEN_PREFIX}{jti}"

    def _user_key(self, user_id: UUID | str) -> str:
        return f"{self.USER_PREFIX}{user_id}"

    def _session_key(self, session_key: str) -> str:
        return f"{self.SESSION_PREFIX}{session_key}"

    # -------------------------
    # SAFETY LAYER
    # -------------------------
    def _safe_ttl(self, expires_at: datetime) -> int:
        delta = expires_at - timezone.now()
        ttl = int(delta.total_seconds())

        # enforce strict positive TTL only
        return ttl if ttl > 0 else 1

    def _normalize_payload(self, payload: dict | None) -> dict:
        return payload or {
            "revoked_at": timezone.now().isoformat()
        }
