from enum import Enum


class SessionStatus(str, Enum):
    """
    Lifecycle states a session can occupy.

    Transitions are strictly one-directional:
        ACTIVE → EXPIRED
        ACTIVE → REVOKED
    An expired or revoked session can never return to ACTIVE.
    """

    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"

    def is_terminal(self) -> bool:
        """Terminal states cannot transition further."""
        return self in (SessionStatus.EXPIRED, SessionStatus.REVOKED)
