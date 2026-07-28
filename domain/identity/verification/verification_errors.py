"""Verification-domain errors."""
from domain.identity.shared import DomainError


class VerificationError(DomainError):
    """Base class for verification lifecycle failures."""


class InvalidVerificationCode(VerificationError):
    """Raised when a verification code is invalid."""


class VerificationChallengeExpired(VerificationError):
    """Raised when a verification challenge is no longer usable."""


class VerificationExpired(VerificationChallengeExpired):
    """Raised when verification has expired."""


class VerificationChallengeConsumed(VerificationError):
    """Raised when a completed challenge is used again."""


class VerificationAttemptLimitExceeded(VerificationError):
    """Raised when too many verification attempts have failed."""


class VerificationAttemptsExhausted(VerificationAttemptLimitExceeded):
    """Raised when no verification attempts remain."""


class VerificationResendTooSoon(VerificationError):
    """Raised when a challenge resend is requested during cooldown."""
