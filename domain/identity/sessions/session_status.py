"""Session status values."""
from enum import Enum


class SessionStatus(str, Enum):
    ACTIVE = "active"
    REVOKED = "revoked"
