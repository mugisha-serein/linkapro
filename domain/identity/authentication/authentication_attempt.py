"""Domain value object for an authentication attempt."""
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class AuthenticationAttempt:
    occurred_at: datetime
    succeeded: bool

    def __post_init__(self) -> None:
        if self.occurred_at.tzinfo is None or self.occurred_at.utcoffset() is None:
            raise ValueError("Authentication attempt time must be timezone-aware")
