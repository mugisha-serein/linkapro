class InvalidEventDetails(ValueError):
    """Raised when event details violate domain invariants."""


class EventNotFound(ValueError):
    """Raised when an event cannot be found."""
