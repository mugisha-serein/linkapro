"""Django cache-backed verification challenge repository."""

from datetime import datetime
import uuid

from django.core.cache import cache

from application.identity.shared.ports import VerificationChallengeRepository
from domain.identity.verification import VerificationChallenge, VerificationPurpose
from domain.shared.utils import utc_now


def _verification_challenge_key(challenge_id: uuid.UUID) -> str:
    return f"identity-verification-challenge:{challenge_id}"


def _serialize_challenge(challenge: VerificationChallenge) -> dict:
    return {
        "id": str(challenge.id),
        "user_id": str(challenge.user_id),
        "purpose": challenge.purpose.value,
        "code_digest": challenge.code_digest,
        "issued_at": challenge.issued_at.isoformat(),
        "expires_at": challenge.expires_at.isoformat(),
        "resend_available_at": challenge.resend_available_at.isoformat(),
        "failed_attempts": challenge.failed_attempts,
        "max_attempts": challenge.max_attempts,
        "succeeded_at": challenge.succeeded_at.isoformat() if challenge.succeeded_at else None,
        "expired_at": challenge.expired_at.isoformat() if challenge.expired_at else None,
    }


def _deserialize_challenge(value) -> VerificationChallenge | None:
    if isinstance(value, VerificationChallenge):
        return value
    if not isinstance(value, dict):
        return None
    try:
        return VerificationChallenge(
            id=uuid.UUID(str(value["id"])),
            user_id=uuid.UUID(str(value["user_id"])),
            purpose=VerificationPurpose(str(value["purpose"])),
            code_digest=str(value["code_digest"]),
            issued_at=datetime.fromisoformat(str(value["issued_at"])),
            expires_at=datetime.fromisoformat(str(value["expires_at"])),
            resend_available_at=datetime.fromisoformat(str(value["resend_available_at"])),
            failed_attempts=int(value.get("failed_attempts", 0)),
            max_attempts=int(value.get("max_attempts", 5)),
            succeeded_at=(
                datetime.fromisoformat(str(value["succeeded_at"]))
                if value.get("succeeded_at")
                else None
            ),
            expired_at=(
                datetime.fromisoformat(str(value["expired_at"]))
                if value.get("expired_at")
                else None
            ),
        )
    except (KeyError, TypeError, ValueError):
        return None


class DjangoVerificationChallengeRepository(VerificationChallengeRepository):
    def save(self, challenge: VerificationChallenge) -> None:
        ttl = max(int((challenge.expires_at - utc_now()).total_seconds()), 1)
        cache.set(
            _verification_challenge_key(challenge.id),
            _serialize_challenge(challenge),
            timeout=ttl,
        )

    def get(self, challenge_id: uuid.UUID) -> VerificationChallenge | None:
        return _deserialize_challenge(cache.get(_verification_challenge_key(challenge_id)))


__all__ = ["DjangoVerificationChallengeRepository"]
