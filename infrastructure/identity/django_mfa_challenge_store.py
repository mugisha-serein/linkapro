"""Django cache-backed MFA setup and replay stores."""

import hashlib
import hmac
import uuid
from datetime import datetime

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured

from application.identity.shared.ports import (
    MfaChallengeRepository,
    MfaEnrollmentRepository,
    MfaEnrollmentState,
    MfaReplayStore,
)
from domain.identity.mfa import MfaChallenge, MfaMethod, MfaPolicy
from domain.identity.verification import VerificationCode
from domain.shared.utils import utc_now


def _enrollment_key(user_id: uuid.UUID) -> str:
    return f"totp_setup_{user_id}"


def _challenge_key(challenge_id: uuid.UUID) -> str:
    return f"mfa-login-challenge:{challenge_id}"


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


def _serialize_challenge(challenge: MfaChallenge) -> dict:
    return {
        "id": str(challenge.id),
        "user_id": str(challenge.user_id),
        "method": challenge.method.value,
        "issued_at": challenge.issued_at.isoformat(),
        "expires_at": challenge.expires_at.isoformat(),
        "max_attempts": challenge.max_attempts,
        "attempt_count": challenge.attempt_count,
        "consumed_at": challenge.consumed_at.isoformat() if challenge.consumed_at else None,
    }


def _deserialize_challenge(value) -> MfaChallenge | None:
    if isinstance(value, MfaChallenge):
        return value
    if not isinstance(value, dict):
        return None
    try:
        return MfaChallenge(
            id=uuid.UUID(str(value["id"])),
            user_id=uuid.UUID(str(value["user_id"])),
            method=MfaMethod(str(value["method"])),
            issued_at=datetime.fromisoformat(str(value["issued_at"])),
            expires_at=datetime.fromisoformat(str(value["expires_at"])),
            max_attempts=int(value["max_attempts"]),
            attempt_count=int(value.get("attempt_count", 0)),
            consumed_at=(
                datetime.fromisoformat(str(value["consumed_at"]))
                if value.get("consumed_at")
                else None
            ),
        )
    except (KeyError, TypeError, ValueError):
        return None


def _serialize_enrollment_state(state: MfaEnrollmentState) -> dict:
    challenge = state.challenge
    return {
        "id": str(challenge.id),
        "user_id": str(challenge.user_id),
        "method": challenge.method.value,
        "issued_at": challenge.issued_at.isoformat(),
        "expires_at": challenge.expires_at.isoformat(),
        "max_attempts": challenge.max_attempts,
        "attempt_count": challenge.attempt_count,
        "consumed_at": challenge.consumed_at.isoformat() if challenge.consumed_at else None,
        "secret": state.secret,
    }


def _deserialize_enrollment_state(value, *, user_id: uuid.UUID) -> MfaEnrollmentState | None:
    if isinstance(value, MfaEnrollmentState):
        return value
    if isinstance(value, str):
        return MfaEnrollmentState(
            challenge=MfaPolicy().issue_challenge(
                user_id=user_id,
                method=MfaMethod.TOTP,
                now=utc_now(),
            ),
            secret=value,
        )
    if not isinstance(value, dict):
        return None
    try:
        secret = str(value["secret"])
        if not secret:
            return None
        challenge = MfaChallenge(
            id=uuid.UUID(str(value["id"])),
            user_id=uuid.UUID(str(value["user_id"])),
            method=MfaMethod(str(value["method"])),
            issued_at=datetime.fromisoformat(str(value["issued_at"])),
            expires_at=datetime.fromisoformat(str(value["expires_at"])),
            max_attempts=int(value["max_attempts"]),
            attempt_count=int(value.get("attempt_count", 0)),
            consumed_at=(
                datetime.fromisoformat(str(value["consumed_at"]))
                if value.get("consumed_at")
                else None
            ),
        )
    except (KeyError, TypeError, ValueError):
        return None
    return MfaEnrollmentState(challenge=challenge, secret=secret)


class DjangoMfaEnrollmentStore(MfaEnrollmentRepository):
    def save(self, state: MfaEnrollmentState, *, ttl: int) -> None:
        cache.set(
            _enrollment_key(state.challenge.user_id),
            _serialize_enrollment_state(state),
            timeout=ttl,
        )

    def get(self, user_id: uuid.UUID) -> MfaEnrollmentState | None:
        return _deserialize_enrollment_state(cache.get(_enrollment_key(user_id)), user_id=user_id)

    def consume(self, user_id: uuid.UUID) -> None:
        cache.delete(_enrollment_key(user_id))


class DjangoMfaChallengeRepository(MfaChallengeRepository):
    def save(self, challenge: MfaChallenge) -> None:
        ttl = max(int((challenge.expires_at - utc_now()).total_seconds()), 1)
        cache.set(_challenge_key(challenge.id), _serialize_challenge(challenge), timeout=ttl)

    def get(self, challenge_id: uuid.UUID) -> MfaChallenge | None:
        return _deserialize_challenge(cache.get(_challenge_key(challenge_id)))


class DjangoMfaReplayStore(MfaReplayStore):
    def has_been_used(self, challenge_id: uuid.UUID, token: VerificationCode) -> bool:
        return bool(cache.get(_replay_key(challenge_id, token)))

    def mark_used(self, challenge_id: uuid.UUID, token: VerificationCode, ttl: int) -> None:
        cache.set(_replay_key(challenge_id, token), "1", timeout=ttl)


__all__ = ["DjangoMfaChallengeRepository", "DjangoMfaEnrollmentStore", "DjangoMfaReplayStore"]
