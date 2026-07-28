"""Pure authentication eligibility policy."""
from dataclasses import dataclass

from domain.identity.account.account import AccountStatus
from domain.identity.account import AccountSuspended, AccountTemporarilyLocked
from domain.identity.shared import DomainError
from .authentication_errors import AuthenticationNotAllowed


@dataclass(frozen=True)
class AuthenticationEligibility:
    allowed: bool
    requires_mfa: bool = False


def evaluate_authentication_eligibility(account) -> AuthenticationEligibility:
    try:
        ensure_authentication_allowed(account)
        allowed = True
    except DomainError:
        allowed = False
    return AuthenticationEligibility(
        allowed=allowed,
        requires_mfa=bool(account.two_factor_enabled) if allowed else False,
    )


def ensure_authentication_allowed(account) -> None:
    if account.status is AccountStatus.SUSPENDED:
        raise AccountSuspended("Account is suspended")
    if account.status is AccountStatus.LOCKED:
        raise AccountTemporarilyLocked("Account is temporarily locked")
    if account.status is not AccountStatus.ACTIVE or not account.is_active or not account.is_verified:
        raise AuthenticationNotAllowed("Account is not allowed to authenticate")
