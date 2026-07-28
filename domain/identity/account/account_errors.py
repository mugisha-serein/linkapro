"""Account-domain errors."""
from domain.identity.shared import DomainError


class AccountCannotBeActivated(DomainError):
    """Raised when an unverified account is moved into an activated state."""


class AccountSuspended(DomainError):
    """Raised when a suspended account attempts a restricted action."""


class AccountTemporarilyLocked(DomainError):
    """Raised when a temporarily locked account attempts a restricted action."""
