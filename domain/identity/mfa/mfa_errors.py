"""MFA-domain errors."""
from domain.identity.shared import DomainError


class MfaError(DomainError):
    """Base class for MFA failures."""


class MfaChallengeExpired(MfaError):
    """Raised when an MFA challenge is expired."""


class RecoveryCodeAlreadyUsed(MfaError):
    """Raised when a recovery code has already been consumed."""
