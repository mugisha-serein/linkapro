"""System clock implementation for identity application ports."""

from datetime import datetime, timezone

from application.identity.shared.ports.clock import Clock


class SystemClock(Clock):
    def now(self) -> datetime:
        return datetime.now(timezone.utc)


__all__ = ["SystemClock"]
