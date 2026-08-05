class InvalidGuestEntry(ValueError):
    """Raised when a guest entry violates domain invariants."""


class GuestNotFound(ValueError):
    """Raised when a guest entry cannot be found."""
