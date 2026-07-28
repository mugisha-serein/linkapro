"""Verification resend cooldown policy."""
from dataclasses import dataclass
from datetime import datetime, timedelta

from domain.identity.shared import SystemClock

from .verification_challenge import VerificationChallenge
from .verification_errors import VerificationResendTooSoon


_system_clock = SystemClock()


def _now_or_system(now: datetime | None) -> datetime:
    return now if now is not None else _system_clock.now()


@dataclass(frozen=True)
class VerificationResendPolicy:
    cooldown: timedelta = timedelta(minutes=10)

    def ensure_can_resend(
        self,
        challenge: VerificationChallenge,
        now: datetime | None = None,
    ) -> None:
        occurred_at = _now_or_system(now)
        if occurred_at < challenge.resend_available_at:
            raise VerificationResendTooSoon("Verification challenge cannot be resent yet")

    def record_resend(
        self,
        challenge: VerificationChallenge,
        now: datetime | None = None,
    ) -> None:
        occurred_at = _now_or_system(now)
        self.ensure_can_resend(challenge, occurred_at)
        challenge.mark_resent(resend_cooldown=self.cooldown, now=occurred_at)
