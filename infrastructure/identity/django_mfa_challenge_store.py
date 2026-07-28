"""Django cache-backed MFA setup and replay stores."""

import hashlib
import hmac
import uuid
from typing import Any

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured

from application.identity.shared.ports import MfaEnrollmentStore, MfaReplayStore
from domain.identity.verification import VerificationCode


def _enrollment_key(user_id: uuid.UUID) -> str:
    return f"totp_setup_{user_id}"


def _mfa_replay_hmac_key() -> bytes:
    key = str(getattr(settings, "MFA_REPLAY_HMAC_KEY", "") or "").strip()
    if not key:
        raise ImproperlyConfigured("MFA_REPLAY_HMAC_KEY must be set")
    return key.encode("utf-8")


def _replay_fingerprint(token: VerificationCode) -> str:
    return hmac.new(
        _mfa_replay_hmac_key(),
        token.value.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _replay_key(challenge_id: uuid.UUID, token: VerificationCode) -> str:
    return f"mfa-replay:{challenge_id}:{_replay_fingerprint(token)}"


class DjangoMfaEnrollmentStore(MfaEnrollmentStore):
    def save(self, user_id: uuid.UUID, state: Any, ttl: int) -> None:
        cache.set(_enrollment_key(user_id), state, timeout=ttl)

    def get(self, user_id: uuid.UUID) -> Any | None:
        return cache.get(_enrollment_key(user_id))

    def consume(self, user_id: uuid.UUID) -> None:
        cache.delete(_enrollment_key(user_id))


class DjangoMfaReplayStore(MfaReplayStore):
    def has_been_used(self, challenge_id: uuid.UUID, token: VerificationCode) -> bool:
        return bool(cache.get(_replay_key(challenge_id, token)))

    def mark_used(self, challenge_id: uuid.UUID, token: VerificationCode, ttl: int) -> None:
        cache.set(_replay_key(challenge_id, token), "1", timeout=ttl)


__all__ = ["DjangoMfaEnrollmentStore", "DjangoMfaReplayStore"]
