"""Authentication-domain errors."""
from domain.identity.shared import DomainError


class AuthenticationError(DomainError):
    """Base class for authentication failures."""


class AuthenticationNotAllowed(AuthenticationError):
    """Raised when account state disallows authentication."""
