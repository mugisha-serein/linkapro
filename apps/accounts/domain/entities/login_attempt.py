# Domain Entity - Pure Business Logic
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID, uuid4


@dataclass(frozen=True)
class LoginAttempt:
    """
    Login attempt domain entity.

    Represents a login attempt in the business domain with security analysis
    and rate limiting logic.
    """

    class Status:
        SUCCESS = "SUCCESS"
        FAILED = "FAILED"
        BLOCKED = "BLOCKED"

    class EventType:
        LOGIN = "LOGIN"
        PASSWORD_ATTEMPT = "PASSWORD_ATTEMPT"
        TOKEN_REFRESH = "TOKEN_REFRESH"
        LOGOUT = "LOGOUT"
        SUSPICIOUS = "SUSPICIOUS"

    user_id: Optional[UUID]
    email: str
    ip_address: str
    user_agent: str
    fingerprint_hash: str
    country_code: Optional[str]
    device_type: Optional[str]
    failure_reason: Optional[str]
    response_time_ms: Optional[int]
    id: UUID = field(default_factory=uuid4)
    status: str = Status.FAILED
    event_type: str = EventType.LOGIN
    risk_score: int = 0
    anomaly_detected: bool = False
    attempt_sequence: int = 1
    created_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        """Validate business invariants."""
        self._validate_email()
        self._validate_status()
        self._validate_event_type()
        self._validate_risk_score()

    def _validate_email(self) -> None:
        """Ensure email is present."""
        if not self.email or "@" not in self.email:
            raise ValueError("Invalid email format")

    def _validate_status(self) -> None:
        """Ensure status is valid."""
        valid_statuses = [self.Status.SUCCESS, self.Status.FAILED, self.Status.BLOCKED]
        if self.status not in valid_statuses:
            raise ValueError(f"Invalid status: {self.status}")

    def _validate_event_type(self) -> None:
        """Ensure event type is valid."""
        valid_types = [self.EventType.LOGIN, self.EventType.PASSWORD_ATTEMPT,
                      self.EventType.TOKEN_REFRESH, self.EventType.LOGOUT, self.EventType.SUSPICIOUS]
        if self.event_type not in valid_types:
            raise ValueError(f"Invalid event type: {self.event_type}")

    def _validate_risk_score(self) -> None:
        """Ensure risk score is within bounds."""
        if not (0 <= self.risk_score <= 100):
            raise ValueError(f"Risk score must be between 0-100: {self.risk_score}")

    def is_successful(self) -> bool:
        """Business rule: check if attempt was successful."""
        return self.status == self.Status.SUCCESS

    def is_suspicious(self) -> bool:
        """Business rule: check if attempt is suspicious."""
        return self.anomaly_detected or self.risk_score >= 70

    def should_trigger_alert(self) -> bool:
        """Business rule: determine if this attempt should trigger security alert."""
        return (
            self.status == self.Status.BLOCKED or
            self.risk_score >= 80 or
            (self.anomaly_detected and self.status == self.Status.FAILED)
        )

    def calculate_risk_score(self, historical_attempts: list[LoginAttempt]) -> int:
        """Business logic: calculate risk score based on patterns."""
        score = 0

        # Recent failures increase risk
        recent_failures = self._count_recent_failures(historical_attempts, minutes=30)
        score += min(recent_failures * 10, 40)

        # Geographic anomalies
        if self._is_geographic_anomaly(historical_attempts):
            score += 25

        # Time-based anomalies
        if self._is_time_anomaly(historical_attempts):
            score += 15

        # Device anomalies
        if self._is_device_anomaly(historical_attempts):
            score += 20

        # Sequence anomalies (rapid attempts)
        if self.attempt_sequence > 3:
            score += 10

        return min(100, score)

    def _count_recent_failures(self, historical_attempts: list[LoginAttempt], minutes: int) -> int:
        """Count failed attempts within time window."""
        cutoff = datetime.now() - timedelta(minutes=minutes)
        return sum(
            1 for attempt in historical_attempts
            if attempt.created_at >= cutoff and attempt.status == self.Status.FAILED
        )

    def _is_geographic_anomaly(self, historical_attempts: list[LoginAttempt]) -> bool:
        """Check if location is unusual compared to history."""
        if not self.country_code:
            return False

        recent_countries = {
            attempt.country_code for attempt in historical_attempts
            if attempt.country_code and attempt.is_successful()
        }

        return self.country_code not in recent_countries and bool(recent_countries)

    def _is_time_anomaly(self, historical_attempts: list[LoginAttempt]) -> bool:
        """Check if login time is unusual."""
        if not historical_attempts:
            return False

        # Get successful login hours
        login_hours = [
            attempt.created_at.hour for attempt in historical_attempts
            if attempt.is_successful()
        ]

        if not login_hours:
            return False

        avg_hour = sum(login_hours) / len(login_hours)
        hour_diff = abs(self.created_at.hour - avg_hour)

        return hour_diff > 8  # More than 8 hours from average

    def _is_device_anomaly(self, historical_attempts: list[LoginAttempt]) -> bool:
        """Check if device fingerprint is unusual."""
        recent_fingerprints = {
            attempt.fingerprint_hash for attempt in historical_attempts
            if attempt.is_successful()
        }

        return self.fingerprint_hash not in recent_fingerprints and bool(recent_fingerprints)

    def mark_as_anomalous(self, reason: str) -> LoginAttempt:
        """Business logic: mark attempt as anomalous."""
        return LoginAttempt(
            id=self.id,
            user_id=self.user_id,
            email=self.email,
            ip_address=self.ip_address,
            user_agent=self.user_agent,
            fingerprint_hash=self.fingerprint_hash,
            country_code=self.country_code,
            device_type=self.device_type,
            status=self.status,
            event_type=self.event_type,
            failure_reason=self.failure_reason,
            risk_score=self.risk_score,
            anomaly_detected=True,
            response_time_ms=self.response_time_ms,
            attempt_sequence=self.attempt_sequence,
            created_at=self.created_at,
        )

    def update_risk_score(self, new_score: int) -> LoginAttempt:
        """Business logic: update risk score."""
        if not (0 <= new_score <= 100):
            raise ValueError(f"Invalid risk score: {new_score}")

        return LoginAttempt(
            id=self.id,
            user_id=self.user_id,
            email=self.email,
            ip_address=self.ip_address,
            user_agent=self.user_agent,
            fingerprint_hash=self.fingerprint_hash,
            country_code=self.country_code,
            device_type=self.device_type,
            status=self.status,
            event_type=self.event_type,
            failure_reason=self.failure_reason,
            risk_score=new_score,
            anomaly_detected=self.anomaly_detected or new_score >= 80,
            response_time_ms=self.response_time_ms,
            attempt_sequence=self.attempt_sequence,
            created_at=self.created_at,
        )

    def should_rate_limit(self, recent_attempts: list[LoginAttempt], window_minutes: int = 15) -> bool:
        """Business rule: check if rate limiting should be applied."""
        cutoff = datetime.now() - timedelta(minutes=window_minutes)
        recent_count = sum(
            1 for attempt in recent_attempts
            if attempt.created_at >= cutoff
        )

        # Allow 5 attempts per 15 minutes, then rate limit
        return recent_count >= 5

    def get_event_hash(self) -> str:
        """Business logic: generate unique event hash for deduplication."""
        import hashlib

        payload = "|".join([
            str(self.user_id or ""),
            self.email,
            self.status,
            self.ip_address,
            self.fingerprint_hash,
            self.created_at.isoformat(),
            str(uuid4()),  # Salt for uniqueness
        ])

        return hashlib.sha256(payload.encode("utf-8")).hexdigest()