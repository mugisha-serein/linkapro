# domain/exceptions/__init__.py
# Pure Python — no framework imports

class DomainException(Exception):
    """Base class for all domain exceptions."""
    pass


# ──────────────────────────────────────────────
# Authentication Exceptions
# ──────────────────────────────────────────────

class AccountInactiveError(DomainException):
    """Raised when an inactive account attempts authentication."""
    pass


class AccountLockedError(DomainException):
    """Raised when a locked account attempts authentication."""

    def __init__(self, locked_until=None):
        self.locked_until = locked_until
        msg = "Account is locked."
        if locked_until:
            msg += f" Try again after {locked_until}."
        super().__init__(msg)


class AuthenticationNotAllowedError(DomainException):
    """Raised when authentication is blocked for any reason."""
    pass


class InvalidCredentialsError(DomainException):
    """Raised when credentials do not satisfy domain rules."""
    pass


# ──────────────────────────────────────────────
# Session Exceptions
# ──────────────────────────────────────────────

class SessionInvalidError(DomainException):
    """Raised when an invalid session is used."""
    pass


class SessionExpiredError(DomainException):
    """Raised when an expired session is used."""
    pass


class SessionRevokedError(DomainException):
    """Raised when a revoked session is used."""
    pass


class SessionOwnershipError(DomainException):
    """Raised when a session does not belong to the requesting user."""
    pass


class DeviceBindingError(DomainException):
    """Raised when a session cannot be bound to a device."""
    pass


# ──────────────────────────────────────────────
# Token Exceptions
# ──────────────────────────────────────────────

class TokenReuseDetectedError(DomainException):
    """Raised when a refresh token is reused — signals theft attempt."""
    pass


class TokenExpiredError(DomainException):
    """Raised when a refresh token is expired."""
    pass


class TokenFamilyCompromisedError(DomainException):
    """Raised when an entire token family is invalidated due to reuse."""
    pass


class TokenOrphanedError(DomainException):
    """Raised when a token has no associated session."""
    pass


# ──────────────────────────────────────────────
# Role / Authorization Exceptions
# ──────────────────────────────────────────────

class RoleAlreadyAssignedError(DomainException):
    """Raised when a role is assigned that the user already holds."""
    pass


class RoleNotFoundError(DomainException):
    """Raised when a role removal or lookup finds no matching role."""
    pass


class UnauthorizedError(DomainException):
    """Raised when a user lacks the required role for an action."""
    pass


# ──────────────────────────────────────────────
# Value Object Exceptions
# ──────────────────────────────────────────────

class InvalidEmailError(DomainException):
    """Raised when an email value object is constructed with invalid data."""
    pass


class InvalidPasswordError(DomainException):
    """Raised when a password value object fails domain rules."""
    pass


class InvalidFingerprintError(DomainException):
    """Raised when a device fingerprint value object is invalid."""
    pass