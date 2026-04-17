# domain/entities/device_fingerprint.py
# Pure Python — no framework, no ORM, no I/O

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from domain.value_objects import DeviceFingerprintValue, UserId, utc_now


# ══════════════════════════════════════════════════════════
# DEVICE FINGERPRINT ENTITY
# Identifies a device context bound to a session.
# Zero-trust: a known fingerprint is NOT a trusted fingerprint.
# ══════════════════════════════════════════════════════════

@dataclass
class DeviceFingerprint:
    """
    Captures the device context in which a session was created.

    Design rules:
    - Never implicitly trusted — possession proves nothing alone.
    - Bound to a specific user; cross-user fingerprint matches
      are always treated as suspicious.
    - 'is_known' means the device was seen before for THIS user;
      it does NOT grant elevated trust.
    - Tracks first-seen and last-seen for risk-engine use (future).

    Zero-trust rules enforced:
    - A new DeviceFingerprint is always untrusted on creation.
    - Trust promotion is explicit and externally triggered.
    - A device seen from a different user is flagged, never promoted.
    """

    id: str
    user_id: UserId
    fingerprint: DeviceFingerprintValue
    user_agent: str
    ip_address: str
    first_seen_at: datetime = field(default_factory=utc_now)
    last_seen_at: datetime = field(default_factory=utc_now)
    is_known: bool = False       # has been seen before for this user
    is_trusted: bool = False     # explicitly promoted by the user (e.g. MFA)
    is_flagged: bool = False     # raised suspicion (e.g. reuse by another user)

    # ── Factory ───────────────────────────────────────────
    @classmethod
    def create(
        cls,
        user_id: UserId,
        fingerprint: DeviceFingerprintValue,
        user_agent: str,
        ip_address: str,
    ) -> "DeviceFingerprint":
        """
        Create a brand-new, untrusted device fingerprint record.
        Always starts unknown and untrusted per zero-trust policy.
        """
        return cls(
            id=str(uuid.uuid4()),
            user_id=user_id,
            fingerprint=fingerprint,
            user_agent=user_agent.strip(),
            ip_address=ip_address.strip(),
        )

    # ── Behaviour ─────────────────────────────────────────

    def mark_seen(self) -> None:
        """
        Record that this device has been seen again.
        Being 'known' does NOT mean 'trusted'.
        """
        self.last_seen_at = utc_now()
        self.is_known = True

    def promote_trust(self) -> None:
        """
        Elevate to trusted after explicit user verification
        (e.g. successful MFA challenge on this device).
        A flagged device can never be trusted.
        """
        if self.is_flagged:
            raise ValueError(
                "A flagged device cannot be promoted to trusted. "
                "Investigate first."
            )
        self.is_trusted = True

    def flag_suspicious(self) -> None:
        """
        Mark device as suspicious (e.g. fingerprint appeared under
        a different user account, or detected in token-reuse chain).
        Revokes trust immediately.
        """
        self.is_flagged = True
        self.is_trusted = False

    def belongs_to(self, user_id: UserId) -> bool:
        """Assert ownership — cross-user match is always False."""
        return self.user_id == user_id

    # ── Identity ──────────────────────────────────────────
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, DeviceFingerprint):
            return NotImplemented
        return self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)

    def __repr__(self) -> str:
        return (
            f"<DeviceFingerprint id={self.id[:8]}… "
            f"known={self.is_known} trusted={self.is_trusted} "
            f"flagged={self.is_flagged}>"
        )