"""Verification challenge policy."""
from dataclasses import dataclass
from datetime import datetime, timedelta
import uuid

from domain.identity.shared import SystemClock

from .verification_challenge import VerificationChallenge
from .verification_code import VerificationCode
from .verification_errors import InvalidVerificationCode
from .verification_purpose import VerificationPurpose


_system_clock = SystemClock()


def _now_or_system(now: datetime | None) -> datetime:
    return now if now is not None else _system_clock.now()


@dataclass(frozen=True)
class VerificationPolicy:
    ttl: timedelta = timedelta(hours=24)
    resend_cooldown: timedelta = timedelta(minutes=10)
    max_attempts: int = 5

    def issue_challenge(
        self,
        *,
        user_id: uuid.UUID,
        purpose: VerificationPurpose | str,
        code: VerificationCode,
        now: datetime | None = None,
    ) -> VerificationChallenge:
        occurred_at = _now_or_system(now)
        return VerificationChallenge.issue(
            user_id=user_id,
            purpose=purpose,
            code=code,
            ttl=self.ttl,
            resend_cooldown=self.resend_cooldown,
            max_attempts=self.max_attempts,
            now=occurred_at,
        )

    def verify_challenge(
        self,
        challenge: VerificationChallenge,
        code: VerificationCode,
        now: datetime | None = None,
    ) -> None:
        challenge.verify(code, now=_now_or_system(now))

    def ensure_terminal_challenge_succeeded(
        self,
        challenge: VerificationChallenge,
        *,
        purpose: VerificationPurpose | str,
    ) -> None:
        if challenge.purpose != VerificationPurpose(purpose):
            raise InvalidVerificationCode("Verification challenge purpose does not match")
        if not challenge.is_succeeded:
            raise InvalidVerificationCode("Verification challenge has not succeeded")
