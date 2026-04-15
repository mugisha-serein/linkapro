# Domain Entity - Pure Business Logic
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4


@dataclass(frozen=True)
class Device:
    """
    Device domain entity.

    Represents a user's device in the business domain with fingerprinting
    and trust assessment logic.
    """

    class TrustLevel:
        UNKNOWN = "UNKNOWN"
        LOW = "LOW"
        MEDIUM = "MEDIUM"
        HIGH = "HIGH"
        BLOCKED = "BLOCKED"

    user_id: UUID
    fingerprint_hash: str
    user_agent: str
    id: UUID = field(default_factory=uuid4)
    device_type: str = ""
    browser: str = ""
    os: str = ""
    timezone: str = ""
    language: str = ""
    ip_cidr: str = ""
    canvas_hash: Optional[str] = None
    webgl_hash: Optional[str] = None
    trust_level: str = TrustLevel.UNKNOWN
    risk_score: int = 0
    first_seen_at: datetime = field(default_factory=datetime.now)
    last_seen_at: datetime = field(default_factory=datetime.now)
    session_count: int = 0
    failed_login_count: int = 0

    def __post_init__(self):
        """Validate business invariants."""
        self._validate_fingerprint()
        self._validate_trust_level()
        self._validate_counts()

    def _validate_fingerprint(self) -> None:
        """Ensure fingerprint is present and reasonable."""
        if not self.fingerprint_hash or len(self.fingerprint_hash) < 32:
            raise ValueError("Invalid fingerprint hash")

    def _validate_trust_level(self) -> None:
        """Ensure trust level is valid."""
        valid_levels = [self.TrustLevel.UNKNOWN, self.TrustLevel.LOW,
                       self.TrustLevel.MEDIUM, self.TrustLevel.HIGH, self.TrustLevel.BLOCKED]
        if self.trust_level not in valid_levels:
            raise ValueError(f"Invalid trust level: {self.trust_level}")

    def _validate_counts(self) -> None:
        """Ensure counts are non-negative."""
        if self.session_count < 0 or self.failed_login_count < 0:
            raise ValueError("Counts cannot be negative")

    def record_successful_session(self) -> Device:
        """Business logic: handle successful session on this device."""
        return Device(
            id=self.id,
            user_id=self.user_id,
            fingerprint_hash=self.fingerprint_hash,
            user_agent=self.user_agent,
            device_type=self.device_type,
            browser=self.browser,
            os=self.os,
            timezone=self.timezone,
            language=self.language,
            ip_cidr=self.ip_cidr,
            canvas_hash=self.canvas_hash,
            webgl_hash=self.webgl_hash,
            trust_level=self._calculate_trust_level(success=True),
            risk_score=max(0, self.risk_score - 5),  # Decrease risk on success
            first_seen_at=self.first_seen_at,
            last_seen_at=datetime.now(),
            session_count=self.session_count + 1,
            failed_login_count=self.failed_login_count,
        )

    def record_failed_login(self) -> Device:
        """Business logic: handle failed login attempt on this device."""
        return Device(
            id=self.id,
            user_id=self.user_id,
            fingerprint_hash=self.fingerprint_hash,
            user_agent=self.user_agent,
            device_type=self.device_type,
            browser=self.browser,
            os=self.os,
            timezone=self.timezone,
            language=self.language,
            ip_cidr=self.ip_cidr,
            canvas_hash=self.canvas_hash,
            webgl_hash=self.webgl_hash,
            trust_level=self._calculate_trust_level(success=False),
            risk_score=min(100, self.risk_score + 10),  # Increase risk on failure
            first_seen_at=self.first_seen_at,
            last_seen_at=self.last_seen_at,
            session_count=self.session_count,
            failed_login_count=self.failed_login_count + 1,
        )

    def _calculate_trust_level(self, success: bool) -> str:
        """Business logic: calculate device trust level."""
        # Simple trust calculation based on usage patterns
        total_attempts = self.session_count + self.failed_login_count + (1 if success else 0)

        if total_attempts == 0:
            return self.TrustLevel.UNKNOWN

        success_rate = self.session_count / total_attempts

        if self.trust_level == self.TrustLevel.BLOCKED:
            return self.TrustLevel.BLOCKED

        if success_rate >= 0.8 and total_attempts >= 3:
            return self.TrustLevel.HIGH
        elif success_rate >= 0.6 and total_attempts >= 2:
            return self.TrustLevel.MEDIUM
        elif success_rate >= 0.3:
            return self.TrustLevel.LOW
        else:
            return self.TrustLevel.UNKNOWN

    def is_trusted(self) -> bool:
        """Business rule: check if device is trusted."""
        return self.trust_level in [self.TrustLevel.MEDIUM, self.TrustLevel.HIGH]

    def is_blocked(self) -> bool:
        """Business rule: check if device is blocked."""
        return self.trust_level == self.TrustLevel.BLOCKED

    def should_be_blocked(self, max_failed_attempts: int = 10) -> bool:
        """Business rule: determine if device should be blocked."""
        return self.failed_login_count >= max_failed_attempts

    def block_device(self, reason: str) -> Device:
        """Business logic: block this device."""
        if not reason.strip():
            raise ValueError("Block reason required")

        return Device(
            id=self.id,
            user_id=self.user_id,
            fingerprint_hash=self.fingerprint_hash,
            user_agent=self.user_agent,
            device_type=self.device_type,
            browser=self.browser,
            os=self.os,
            timezone=self.timezone,
            language=self.language,
            ip_cidr=self.ip_cidr,
            canvas_hash=self.canvas_hash,
            webgl_hash=self.webgl_hash,
            trust_level=self.TrustLevel.BLOCKED,
            risk_score=100,
            first_seen_at=self.first_seen_at,
            last_seen_at=self.last_seen_at,
            session_count=self.session_count,
            failed_login_count=self.failed_login_count,
        )

    def matches_fingerprint(self, other_fingerprint: str) -> bool:
        """Business rule: check if fingerprints match."""
        return self.fingerprint_hash == other_fingerprint

    def has_changed_attributes(self, user_agent: str, ip_address: str) -> bool:
        """Business rule: check if device attributes have changed."""
        return (
            self.user_agent != user_agent or
            not self._ip_in_cidr(ip_address)
        )

    def _ip_in_cidr(self, ip_address: str) -> bool:
        """Simple check if IP is in device's CIDR range."""
        if not self.ip_cidr:
            return False
        # Simplified check - in real implementation would use proper CIDR logic
        return ip_address.startswith(self.ip_cidr.split('/')[0])

    def calculate_risk_score(self) -> int:
        """Business logic: calculate comprehensive risk score."""
        score = 0

        # Trust level factors
        if self.trust_level == self.TrustLevel.UNKNOWN:
            score += 30
        elif self.trust_level == self.TrustLevel.LOW:
            score += 20
        elif self.trust_level == self.TrustLevel.BLOCKED:
            score += 100

        # Usage pattern factors
        total_attempts = self.session_count + self.failed_login_count
        if total_attempts > 0:
            failure_rate = self.failed_login_count / total_attempts
            score += int(failure_rate * 50)

        # Age factors (newer devices are riskier)
        days_old = (datetime.now() - self.first_seen_at).days
        if days_old < 1:
            score += 15
        elif days_old < 7:
            score += 5

        return min(100, max(0, score))