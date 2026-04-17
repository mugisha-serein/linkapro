"""
Domain-level exceptions.
All exceptions are pure domain concerns — no HTTP status codes, no framework coupling.
"""


class DomainException(Exception):
    """Base for all domain exceptions."""


# --- Authentication ---

class AuthenticationError(DomainException):
    """Authentication attempt failed for a business rule reason."""


class AccountInactiveError(AuthenticationError):
    """Account is not active and cannot authenticate."""


class AccountLockedError(AuthenticationError):
    """Account is locked due to repeated failed attempts."""


class InvalidCredentialsError(AuthenticationError):
    """Credentials did not match — generic to prevent enumeration."""


# --- Session ---

class SessionError(DomainException):
    """Base for session-related violations."""


class SessionExpiredError(SessionError):
    """Session has passed its validity window."""


class SessionRevokedError(SessionError):
    """Session was explicitly revoked."""


class SessionDeviceMismatchError(SessionError):
    """Session is being used from an unexpected device context."""


class SessionNotEligibleError(SessionError):
    """User does not meet the conditions to create a new session."""


# --- Token ---

class TokenError(DomainException):
    """Base for refresh token violations."""


class TokenAlreadyUsedError(TokenError):
    """Refresh token reuse detected — possible token theft."""


class TokenFamilyCompromisedError(TokenError):
    """Token family is compromised. All sessions in family must be invalidated."""


class TokenExpiredError(TokenError):
    """Token is past its validity window."""


class TokenOrphanError(TokenError):
    """Token cannot exist without an associated session."""

class TokenReuseDetectedError(DomainException):
    """Raised when a refresh token is reused — signals theft attempt."""
    pass

class TokenOrphanedError(DomainException):
    """Raised when a token has no associated session."""
    pass

# --- Role / Authorization ---

class AuthorizationError(DomainException):
    """Authorization rule violation."""


class RoleAlreadyAssignedError(AuthorizationError):
    """Role is already assigned to this user."""


class RoleNotFoundError(AuthorizationError):
    """Role is not assigned to this user."""


# --- Value Objects ---

class InvalidEmailError(DomainException):
    """Email address failed structural validation."""


class InvalidValueError(DomainException):
    """A value object received an invalid value."""
