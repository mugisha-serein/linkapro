from enum import Enum


class EventType(str, Enum):
    WEDDING = "wedding"
    TRAVEL = "travel"
    CORPORATE = "corporate"
    OTHER = "other"

