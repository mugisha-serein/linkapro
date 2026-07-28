"""Identity authentication domain model."""
from .account_lockout_policy import AccountLockoutDecision, AccountLockoutPolicy
from .authentication_attempt import AuthenticationAttempt
from .authentication_errors import AuthenticationError, AuthenticationNotAllowed
from .authentication_policy import (
    AuthenticationEligibility,
    ensure_authentication_allowed,
    evaluate_authentication_eligibility,
)
from .authentication_events import UserLoggedIn
from .failed_attempt_counter import FailedAttemptCounter

__all__ = [
    "AccountLockoutDecision",
    "AccountLockoutPolicy",
    "AuthenticationAttempt",
    "AuthenticationError",
    "AuthenticationEligibility",
    "AuthenticationNotAllowed",
    "FailedAttemptCounter",
    "UserLoggedIn",
    "ensure_authentication_allowed",
    "evaluate_authentication_eligibility",
]
