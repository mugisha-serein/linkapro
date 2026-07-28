import uuid
from datetime import timedelta

import pytest

from domain.identity.account import AccountStatus, AccountSuspended, AccountTemporarilyLocked, User, UserRole
from domain.identity.authentication import (
    AccountLockoutPolicy,
    AuthenticationNotAllowed,
    FailedAttemptCounter,
    ensure_authentication_allowed,
    evaluate_authentication_eligibility,
)
from domain.identity.credentials import Email, PasswordHash
from domain.identity.shared import SystemClock


def _user(*, status: AccountStatus, two_factor_enabled: bool = False) -> User:
    return User(
        id=uuid.uuid4(),
        email=Email("user@example.com"),
        password_hash=PasswordHash("hash"),
        first_name="Test",
        last_name="User",
        role=UserRole.PLANNER,
        status=status,
        two_factor_enabled=two_factor_enabled,
    )


@pytest.mark.parametrize(
    "status",
    [
        AccountStatus.PENDING_VERIFICATION,
        AccountStatus.DEACTIVATED,
        AccountStatus.DEACTIVATED_PENDING_VERIFICATION,
        AccountStatus.SUSPENDED,
        AccountStatus.LOCKED,
    ],
)
def test_ineligible_account_statuses_cannot_authenticate(status):
    decision = evaluate_authentication_eligibility(_user(status=status))

    assert decision.allowed is False
    assert decision.requires_mfa is False


def test_active_verified_account_can_authenticate_without_mfa():
    decision = evaluate_authentication_eligibility(_user(status=AccountStatus.ACTIVE))

    assert decision.allowed is True
    assert decision.requires_mfa is False


def test_active_verified_account_can_require_mfa():
    decision = evaluate_authentication_eligibility(
        _user(status=AccountStatus.ACTIVE, two_factor_enabled=True)
    )

    assert decision.allowed is True
    assert decision.requires_mfa is True


def test_authentication_policy_raises_specific_domain_errors():
    with pytest.raises(AccountSuspended):
        ensure_authentication_allowed(_user(status=AccountStatus.SUSPENDED))
    with pytest.raises(AccountTemporarilyLocked):
        ensure_authentication_allowed(_user(status=AccountStatus.LOCKED))
    with pytest.raises(AuthenticationNotAllowed):
        ensure_authentication_allowed(_user(status=AccountStatus.PENDING_VERIFICATION))


def test_account_lockout_policy_locks_after_max_failures():
    now = SystemClock().now()
    policy = AccountLockoutPolicy(
        max_failures=2,
        observation_window=timedelta(minutes=15),
        lock_duration=timedelta(minutes=10),
    )

    counter = policy.record_failure(FailedAttemptCounter(), now=now)
    counter = policy.record_failure(counter, now=now + timedelta(seconds=1))
    decision = policy.evaluate(counter, now=now + timedelta(seconds=2))

    assert decision.locked is True
    assert decision.failed_attempts == 2
    assert decision.locked_until == now + timedelta(seconds=1, minutes=10)


def test_account_lockout_policy_ignores_failures_outside_observation_window():
    now = SystemClock().now()
    policy = AccountLockoutPolicy(
        max_failures=2,
        observation_window=timedelta(minutes=15),
        lock_duration=timedelta(minutes=10),
    )

    counter = policy.record_failure(FailedAttemptCounter(), now=now - timedelta(minutes=20))
    counter = policy.record_failure(counter, now=now)
    decision = policy.evaluate(counter, now=now)

    assert decision.locked is False
    assert decision.failed_attempts == 1


def test_account_lockout_policy_resets_on_success():
    now = SystemClock().now()
    policy = AccountLockoutPolicy(
        max_failures=2,
        observation_window=timedelta(minutes=15),
        lock_duration=timedelta(minutes=10),
    )
    counter = policy.record_failure(FailedAttemptCounter(), now=now)

    counter = policy.record_success(counter)
    decision = policy.evaluate(counter, now=now)

    assert decision.locked is False
    assert decision.failed_attempts == 0
