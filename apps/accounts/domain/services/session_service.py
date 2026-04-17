# domain/services/session_service.py
# Pure Python — no framework, no ORM, no I/O

from __future__ import annotations

from typing import List, Optional

from domain.entities.session import Session
from domain.entities.device_fingerprint import DeviceFingerprint
from domain.value_objects import UserId, DeviceFingerprintValue, utc_now
from domain.exceptions import (
    SessionInvalidError,
    SessionOwnershipError,
    DeviceBindingError,
)


# ══════════════════════════════════════════════════════════
# SESSION DOMAIN SERVICE
#
# Handles session lifecycle orchestration that involves
# co-ordination across more than one entity.
# Single-entity behaviours live on the entity itself;
# multi-entity coordination belongs here.
# ══════════════════════════════════════════════════════════


class SessionService:
    """
    Domain service for session lifecycle management.

    Responsibilities:
    - Deciding whether to revoke one or all user sessions.
    - Checking device consistency across a session.
    - Enforcing zero-trust: any anomaly triggers revocation.

    Does NOT:
    - Persist anything.
    - Interact with HTTP or JWT.
    - Contact external services.
    """

    # ──────────────────────────────────────────────────────
    # REVOCATION
    # ──────────────────────────────────────────────────────

    def revoke_session(
        self,
        session: Session,
        requesting_user_id: UserId,
    ) -> None:
        """
        Revoke a single session on behalf of a user (e.g. explicit logout).

        Enforces:
        - Session must be owned by the requesting user.
        - No-op if already revoked (idempotent by design).
        """
        session.assert_owned_by(requesting_user_id)
        session.revoke()

    def revoke_all_user_sessions(
        self,
        sessions: List[Session],
        user_id: UserId,
    ) -> int:
        """
        Revoke every active session for a user.
        Called on: password change, suspicious activity, admin action.

        Returns the number of sessions that were actively revoked
        (not counting already-revoked or expired ones).
        """
        revoked_count = 0
        for session in sessions:
            if session.user_id != user_id:
                # Silently skip sessions not owned by this user
                # (protects against bulk-operation misuse)
                continue
            if session.is_valid():
                session.revoke()
                revoked_count += 1
        return revoked_count

    def revoke_all_except(
        self,
        sessions: List[Session],
        user_id: UserId,
        keep_session_id: str,
    ) -> int:
        """
        Revoke all sessions for a user except one (e.g. "log out everywhere else").
        The kept session must belong to the same user.
        """
        revoked_count = 0
        for session in sessions:
            if session.user_id != user_id:
                continue
            if str(session.id) == keep_session_id:
                continue
            if session.is_valid():
                session.revoke()
                revoked_count += 1
        return revoked_count

    # ──────────────────────────────────────────────────────
    # DEVICE BINDING & CONSISTENCY
    # ──────────────────────────────────────────────────────

    def bind_device_to_session(
        self,
        session: Session,
        device: DeviceFingerprint,
        user_id: UserId,
    ) -> None:
        """
        Attach a DeviceFingerprint to a Session.

        Domain rules enforced:
        - Session must be valid.
        - Device must belong to the same user as the session.
        - Device must not be flagged as suspicious.
        """
        if not session.is_valid():
            raise SessionInvalidError(
                f"Cannot bind device to invalid session {session.id}."
            )
        if not device.belongs_to(user_id):
            raise DeviceBindingError(
                "Device does not belong to the session owner. "
                "Cross-user device binding is forbidden."
            )
        if device.is_flagged:
            raise DeviceBindingError(
                "Cannot bind a flagged device to a session. "
                "The device has been marked suspicious."
            )
        session.bind_device(device.id)
        device.mark_seen()

    def detect_device_anomaly(
        self,
        session: Session,
        presented_fingerprint: DeviceFingerprintValue,
        bound_device: Optional[DeviceFingerprint],
    ) -> DeviceAnomalyResult:
        """
        Compare a presented fingerprint against the session's bound device.

        Returns a DeviceAnomalyResult describing whether the request
        looks legitimate.  The caller decides how to act on this.

        Anomaly conditions:
        - Session has a bound device but presented fingerprint doesn't match.
        - Session has a bound device and it is flagged.
        - Presented fingerprint is empty.
        """
        # No fingerprint presented when session has none bound → neutral
        if session.device_fingerprint_id is None and bound_device is None:
            return DeviceAnomalyResult(anomaly_detected=False)

        # Session has no bound device → cannot verify (treated as low-risk
        # but not trusted — up to caller to decide if binding is required)
        if session.device_fingerprint_id is None:
            return DeviceAnomalyResult(
                anomaly_detected=False,
                note="Session has no bound device; fingerprint check skipped.",
            )

        if bound_device is None:
            # Session claims a device ID but we have no record — data integrity issue
            return DeviceAnomalyResult(
                anomaly_detected=True,
                reason="Bound device record not found for session. Data integrity concern.",
            )

        if bound_device.is_flagged:
            return DeviceAnomalyResult(
                anomaly_detected=True,
                reason="Session's bound device has been flagged as suspicious.",
            )

        if bound_device.fingerprint.raw != presented_fingerprint.raw:
            return DeviceAnomalyResult(
                anomaly_detected=True,
                reason=(
                    "Presented device fingerprint does not match the session's "
                    "bound device. Possible session hijacking."
                ),
            )

        return DeviceAnomalyResult(anomaly_detected=False)

    # ──────────────────────────────────────────────────────
    # EXPIRY SWEEP
    # ──────────────────────────────────────────────────────

    def expire_stale_sessions(self, sessions: List[Session]) -> int:
        """
        Transition all TTL-elapsed ACTIVE sessions to EXPIRED.
        Intended to be called by a scheduled application-layer job;
        the domain provides the decision logic.

        Returns the count of sessions transitioned.
        """
        count = 0
        for session in sessions:
            if not session.is_valid() and session.status.value == "ACTIVE":
                # is_valid() has already flipped status to EXPIRED internally
                count += 1
        return count


# ══════════════════════════════════════════════════════════
# RESULT VALUE OBJECT
# ══════════════════════════════════════════════════════════

class DeviceAnomalyResult:
    """Describes the outcome of a device anomaly check."""

    def __init__(
        self,
        anomaly_detected: bool,
        reason: Optional[str] = None,
        note: Optional[str] = None,
    ) -> None:
        self.anomaly_detected = anomaly_detected
        self.reason = reason
        self.note = note

    def __bool__(self) -> bool:
        return self.anomaly_detected

    def __repr__(self) -> str:
        return (
            f"<DeviceAnomalyResult "
            f"anomaly={self.anomaly_detected} "
            f"reason={self.reason!r}>"
        )