from datetime import UTC, datetime, timedelta
import uuid

import pytest

from domain.identity.account import User, UserRole
from domain.identity.credentials import Email, PasswordHash
from domain.identity.verification import (
    InvalidVerificationCode,
    UserVerified,
    VerificationChallengeExpired,
    VerificationChallengeExpiredEvent,
    VerificationChallengeIssued,
    VerificationChallengeSucceeded,
    VerificationCode,
    VerificationPolicy,
    VerificationPurpose,
    VerificationResendPolicy,
    VerificationResendTooSoon,
)


NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


def _user() -> User:
    return User(
        id=uuid.uuid4(),
        email=Email("verify@example.com"),
        password_hash=PasswordHash("hash"),
        first_name="Verify",
        last_name="User",
        role=UserRole.PLANNER,
        is_verified=False,
    )


def test_verification_policy_issues_challenge_without_raw_code_event_data():
    policy = VerificationPolicy(ttl=timedelta(minutes=30), resend_cooldown=timedelta(minutes=5))
    code = VerificationCode("123456")

    challenge = policy.issue_challenge(
        user_id=uuid.uuid4(),
        purpose=VerificationPurpose.EMAIL,
        code=code,
        now=NOW,
    )

    assert challenge.code_digest == code.digest
    assert challenge.expires_at == NOW + timedelta(minutes=30)
    assert challenge.resend_available_at == NOW + timedelta(minutes=5)
    event = challenge.pull_events()[0]
    assert isinstance(event, VerificationChallengeIssued)
    assert event.purpose == VerificationPurpose.EMAIL
    assert not hasattr(event, "code")


def test_successful_challenge_allows_mark_verified_terminal_transition():
    user = _user()
    policy = VerificationPolicy()
    code = VerificationCode("654321")
    challenge = policy.issue_challenge(
        user_id=user.id,
        purpose=VerificationPurpose.EMAIL,
        code=code,
        now=NOW,
    )
    challenge.pull_events()

    policy.verify_challenge(challenge, code, now=NOW + timedelta(minutes=1))
    user.mark_verified(challenge=challenge, now=NOW + timedelta(minutes=1))

    challenge_events = challenge.pull_events()
    user_events = user.pull_events()
    assert user.is_verified is True
    assert isinstance(challenge_events[0], VerificationChallengeSucceeded)
    assert isinstance(user_events[0], UserVerified)


def test_unsuccessful_challenge_cannot_mark_verified():
    user = _user()
    challenge = VerificationPolicy().issue_challenge(
        user_id=user.id,
        purpose=VerificationPurpose.EMAIL,
        code=VerificationCode("123456"),
        now=NOW,
    )

    with pytest.raises(InvalidVerificationCode):
        user.mark_verified(challenge=challenge, now=NOW)


def test_expired_challenge_records_expiry_and_rejects_verification():
    policy = VerificationPolicy(ttl=timedelta(seconds=1))
    challenge = policy.issue_challenge(
        user_id=uuid.uuid4(),
        purpose=VerificationPurpose.EMAIL,
        code=VerificationCode("123456"),
        now=NOW,
    )
    challenge.pull_events()

    with pytest.raises(VerificationChallengeExpired):
        policy.verify_challenge(
            challenge,
            VerificationCode("123456"),
            now=NOW + timedelta(seconds=2),
        )

    event = challenge.pull_events()[0]
    assert isinstance(event, VerificationChallengeExpiredEvent)


def test_resend_policy_enforces_cooldown_and_records_resend():
    policy = VerificationPolicy(resend_cooldown=timedelta(minutes=10))
    resend_policy = VerificationResendPolicy(cooldown=timedelta(minutes=10))
    challenge = policy.issue_challenge(
        user_id=uuid.uuid4(),
        purpose=VerificationPurpose.EMAIL,
        code=VerificationCode("123456"),
        now=NOW,
    )
    challenge.pull_events()

    with pytest.raises(VerificationResendTooSoon):
        resend_policy.record_resend(challenge, now=NOW + timedelta(minutes=5))

    resend_policy.record_resend(challenge, now=NOW + timedelta(minutes=10))
    [event] = challenge.pull_events()
    assert event.resend_available_at == NOW + timedelta(minutes=20)
