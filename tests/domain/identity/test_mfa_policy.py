from datetime import timedelta
import uuid

import pyotp

from domain.identity.mfa import MfaMethod, MfaPolicy, RecoveryCode, TOTPSecret
from domain.identity.shared import SystemClock


def test_mfa_policy_issues_expiring_challenge():
    now = SystemClock().now()
    policy = MfaPolicy(challenge_ttl=timedelta(minutes=3), max_attempts=5)

    challenge = policy.issue_challenge(user_id=uuid.uuid4(), method=MfaMethod.TOTP, now=now)

    assert challenge.method is MfaMethod.TOTP
    assert challenge.issued_at == now
    assert challenge.expires_at == now + timedelta(minutes=3)
    assert challenge.max_attempts == 5


def test_mfa_policy_accepts_valid_totp_and_consumes_challenge():
    now = SystemClock().now()
    secret = TOTPSecret(pyotp.random_base32())
    token = pyotp.TOTP(secret.reveal_for_totp_verification()).at(now)
    policy = MfaPolicy(challenge_ttl=timedelta(minutes=3), max_attempts=5)
    challenge = policy.issue_challenge(user_id=uuid.uuid4(), method=MfaMethod.TOTP, now=now)

    result = policy.verify_totp(challenge=challenge, secret=secret, token=token, now=now)

    assert result.accepted is True
    assert result.challenge.consumed_at == now


def test_mfa_policy_rejects_expired_challenge():
    now = SystemClock().now()
    secret = TOTPSecret(pyotp.random_base32())
    token = pyotp.TOTP(secret.reveal_for_totp_verification()).at(now)
    policy = MfaPolicy(challenge_ttl=timedelta(minutes=3), max_attempts=5)
    challenge = policy.issue_challenge(user_id=uuid.uuid4(), method=MfaMethod.TOTP, now=now)

    result = policy.verify_totp(
        challenge=challenge,
        secret=secret,
        token=token,
        now=now + timedelta(minutes=4),
    )

    assert result.accepted is False
    assert result.challenge.attempt_count == 0


def test_mfa_policy_enforces_attempt_limit():
    now = SystemClock().now()
    policy = MfaPolicy(challenge_ttl=timedelta(minutes=3), max_attempts=1)
    challenge = policy.issue_challenge(user_id=uuid.uuid4(), method=MfaMethod.TOTP, now=now)
    secret = TOTPSecret(pyotp.random_base32())

    first = policy.verify_totp(challenge=challenge, secret=secret, token="000000", now=now)
    second = policy.verify_totp(
        challenge=first.challenge,
        secret=secret,
        token=pyotp.TOTP(secret.reveal_for_totp_verification()).at(now),
        now=now,
    )

    assert first.accepted is False
    assert first.challenge.attempt_count == 1
    assert second.accepted is False


def test_recovery_codes_are_single_use():
    now = SystemClock().now()
    policy = MfaPolicy()
    recovery_code = RecoveryCode(id=uuid.uuid4(), code_hash="hashed-code")

    first = policy.consume_recovery_code(
        recovery_codes=[recovery_code],
        presented_code="code",
        hash_code=lambda value: "hashed-code",
        now=now,
    )
    second = policy.consume_recovery_code(
        recovery_codes=first.recovery_codes,
        presented_code="code",
        hash_code=lambda value: "hashed-code",
        now=now + timedelta(seconds=1),
    )

    assert first.accepted is True
    assert first.recovery_codes[0].used_at == now
    assert second.accepted is False
    assert second.recovery_codes[0].used_at == now
