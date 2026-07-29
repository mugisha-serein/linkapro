"""Pure MFA policy for challenge verification and recovery-code consumption."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable, ClassVar, Iterable
import uuid

import pyotp

from .mfa_challenge import MfaChallenge
from .mfa_errors import MfaChallengeExpired
from .mfa_method import MfaMethod
from .recovery_code import RecoveryCode
from .totp_secret import TOTPSecret


@dataclass(frozen=True)
class MfaVerificationResult:
    accepted: bool
    challenge: MfaChallenge


@dataclass(frozen=True)
class RecoveryCodeConsumptionResult:
    accepted: bool
    recovery_codes: tuple[RecoveryCode, ...]


@dataclass(frozen=True)
class MfaPolicy:
    DEFAULT_CHALLENGE_TTL: ClassVar[timedelta] = timedelta(seconds=600)
    DEFAULT_MAX_ATTEMPTS: ClassVar[int] = 5

    challenge_ttl: timedelta = DEFAULT_CHALLENGE_TTL
    max_attempts: int = DEFAULT_MAX_ATTEMPTS

    def __post_init__(self) -> None:
        if self.challenge_ttl.total_seconds() <= 0:
            raise ValueError("MFA challenge_ttl must be positive")
        if self.max_attempts <= 0:
            raise ValueError("MFA max_attempts must be positive")

    def issue_challenge(
        self,
        *,
        user_id: uuid.UUID,
        method: MfaMethod,
        now: datetime,
    ) -> MfaChallenge:
        self._validate_now(now)
        return MfaChallenge(
            id=uuid.uuid4(),
            user_id=user_id,
            method=method,
            issued_at=now,
            expires_at=now + self.challenge_ttl,
            max_attempts=self.max_attempts,
        )

    @classmethod
    def default_challenge_ttl(cls) -> timedelta:
        return cls.DEFAULT_CHALLENGE_TTL

    @classmethod
    def default_max_attempts(cls) -> int:
        return cls.DEFAULT_MAX_ATTEMPTS

    def challenge_ttl_seconds(self) -> int:
        return int(self.challenge_ttl.total_seconds())

    def remaining_challenge_ttl_seconds(self, challenge: MfaChallenge, *, now: datetime) -> int:
        self._validate_now(now)
        return max(int((challenge.expires_at - now).total_seconds()), 1)

    def verify_challenge(
        self,
        *,
        challenge: MfaChallenge,
        accepted: bool,
        now: datetime,
    ) -> MfaVerificationResult:
        self._validate_now(now)
        try:
            can_attempt = challenge.can_attempt(now=now)
        except MfaChallengeExpired:
            return MfaVerificationResult(False, challenge)
        if challenge.method is not MfaMethod.TOTP or not can_attempt:
            return MfaVerificationResult(False, challenge)
        if accepted:
            return MfaVerificationResult(True, challenge.consume(now=now))
        return MfaVerificationResult(False, challenge.record_failed_attempt())

    def verify_totp(
        self,
        *,
        challenge: MfaChallenge,
        secret: TOTPSecret,
        token: str,
        now: datetime,
    ) -> MfaVerificationResult:
        accepted = pyotp.TOTP(secret.reveal_for_totp_verification()).verify(token, for_time=now)
        return self.verify_challenge(
            challenge=challenge,
            accepted=accepted,
            now=now,
        )

    def consume_recovery_code(
        self,
        *,
        recovery_codes: Iterable[RecoveryCode],
        presented_code: str,
        hash_code: Callable[[str], str],
        now: datetime,
    ) -> RecoveryCodeConsumptionResult:
        self._validate_now(now)
        presented_hash = hash_code(presented_code)
        updated_codes = []
        accepted = False
        for recovery_code in recovery_codes:
            if not accepted and recovery_code.matches(presented_hash):
                if recovery_code.is_used:
                    return RecoveryCodeConsumptionResult(False, tuple(recovery_codes))
                updated_codes.append(recovery_code.consume(now=now))
                accepted = True
            else:
                updated_codes.append(recovery_code)
        return RecoveryCodeConsumptionResult(accepted, tuple(updated_codes))

    @staticmethod
    def can_enable_method(method: MfaMethod, *, already_enabled: bool) -> bool:
        if method is not MfaMethod.TOTP:
            raise ValueError("Unsupported MFA method")
        return not already_enabled

    @staticmethod
    def can_disable_method(method: MfaMethod, *, enabled: bool) -> bool:
        if method is not MfaMethod.TOTP:
            raise ValueError("Unsupported MFA method")
        return enabled

    @staticmethod
    def _validate_now(now: datetime) -> None:
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("Current time must be timezone-aware")
