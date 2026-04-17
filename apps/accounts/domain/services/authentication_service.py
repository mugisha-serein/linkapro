# domain/services/authentication_service.py
# Pure Python — no framework, no ORM, no I/O, no external libraries

from __future__ import annotations

from typing import Optional

from domain.entities.user import User
from domain.entities.login_activity import LoginActivity
from domain.entities.session import Session
from domain.entities.device_fingerprint import DeviceFingerprint
from domain.value_objects import (
    Email,
    HashedPassword,
    DeviceFingerprintValue,
    SessionId,
    UserId,
)
from domain.exceptions import (
    AccountInactiveError,
    AccountLockedError,
    AuthenticationNotAllowedError,
    InvalidCredentialsError,
)


# ══════════════════════════════════════════════════════════
# AUTHENTICATION DOMAIN SERVICE
#
# Orchestrates authentication decisions using only domain
# entities and value objects.
#
# What it does NOT do:
# - Does not query a database
# - Does not issue JWT tokens
# - Does not send emails or SMS
# - Does not know about HTTP requests
#
# The application layer is responsible for:
# - Loading the User from a repository
# - Persisting the resulting Session and LoginActivity
# - Issuing infrastructure-level tokens (JWT, cookies)
# ══════════════════════════════════════════════════════════


class AuthenticationService:
    """
    Pure domain service that evaluates authentication eligibility
    and produces domain decisions (not infrastructure side-effects).

    All methods are stateless and deterministic given the same inputs.
    """

    # ──────────────────────────────────────────────────────
    # PRIMARY AUTHENTICATION FLOW
    # ──────────────────────────────────────────────────────

    def authenticate(
        self,
        user: User,
        presented_password_hash: str,
        ip_address: str,
        user_agent: str,
        device_fingerprint_value: Optional[DeviceFingerprintValue] = None,
        session_ttl_minutes: int = 30,
        token_ttl_days: int = 7,
    ) -> AuthenticationResult:
        """
        Evaluate whether authentication should succeed.

        Steps (in zero-trust order):
        1. Assert account is eligible (active + unlocked).
        2. Verify password hash matches.
        3. Record success or failure on the User aggregate.
        4. If success: create Session + DeviceFingerprint + LoginActivity.
        5. Return a result object; never raise on recoverable failure.

        Raises:
        - AccountInactiveError      → account is inactive (terminal block)
        - AccountLockedError        → account is locked (temporary block)
        - InvalidCredentialsError   → password mismatch (after side-effects recorded)

        The caller (application layer) MUST persist:
        - The mutated User (updated failed_attempts / locked_until)
        - The LoginActivity record
        - The Session (on success)
        - The DeviceFingerprint (on success)
        """

        # ── Step 1: Eligibility check (raises if blocked) ─
        try:
            user.assert_can_authenticate()
        except (AccountInactiveError, AccountLockedError) as exc:
            blocked_activity = LoginActivity.record_blocked(
                user_id=user.id,
                ip_address=ip_address,
                user_agent=user_agent,
                failure_reason=str(exc),
                device_fingerprint_raw=(
                    str(device_fingerprint_value) if device_fingerprint_value else None
                ),
            )
            return AuthenticationResult.blocked(activity=blocked_activity, reason=str(exc))

        # ── Step 2: Credential verification ───────────────
        if not user.hashed_password.matches(presented_password_hash):
            user.register_failed_attempt()
            failed_activity = LoginActivity.record_failure(
                user_id=user.id,
                ip_address=ip_address,
                user_agent=user_agent,
                failure_reason="Invalid credentials.",
                device_fingerprint_raw=(
                    str(device_fingerprint_value) if device_fingerprint_value else None
                ),
            )
            return AuthenticationResult.failed(
                activity=failed_activity,
                reason="Invalid credentials.",
                user=user,
            )

        # ── Step 3: Build session ──────────────────────────
        session = Session.create(
            user_id=user.id,
            ip_address=ip_address,
            user_agent=user_agent,
            ttl_minutes=session_ttl_minutes,
        )

        # ── Step 4: Device fingerprint binding ────────────
        device: Optional[DeviceFingerprint] = None
        if device_fingerprint_value is not None:
            device = DeviceFingerprint.create(
                user_id=user.id,
                fingerprint=device_fingerprint_value,
                user_agent=user_agent,
                ip_address=ip_address,
            )
            session.bind_device(device.id)

        # ── Step 5: Record success on aggregate ───────────
        user.record_successful_login()

        success_activity = LoginActivity.record_success(
            user_id=user.id,
            session_id=session.id,
            ip_address=ip_address,
            user_agent=user_agent,
            device_fingerprint_raw=(
                str(device_fingerprint_value) if device_fingerprint_value else None
            ),
        )

        return AuthenticationResult.success(
            session=session,
            device=device,
            activity=success_activity,
            user=user,
        )

    # ──────────────────────────────────────────────────────
    # SESSION VALIDATION
    # ──────────────────────────────────────────────────────

    def validate_session(
        self,
        session: Session,
        requesting_user_id: UserId,
        presented_device_fingerprint_id: Optional[str] = None,
    ) -> SessionValidationResult:
        """
        Confirm that a session may be used by the requesting principal.

        Checks (in order):
        1. Session is valid (ACTIVE, within TTL).
        2. Session belongs to the requesting user.
        3. If a device fingerprint is presented, it matches the bound one.

        Returns a result value object; the caller decides how to respond.
        """
        # ── Validity ───────────────────────────────────────
        if not session.is_valid():
            return SessionValidationResult(valid=False, reason="Session is invalid or expired.")

        # ── Ownership ──────────────────────────────────────
        try:
            session.assert_owned_by(requesting_user_id)
        except Exception as exc:
            return SessionValidationResult(valid=False, reason=str(exc))

        # ── Device consistency ─────────────────────────────
        if (
            presented_device_fingerprint_id is not None
            and session.device_fingerprint_id is not None
            and not session.is_bound_to_device(presented_device_fingerprint_id)
        ):
            return SessionValidationResult(
                valid=False,
                reason="Device fingerprint mismatch — possible session hijack.",
            )

        return SessionValidationResult(valid=True)


# ══════════════════════════════════════════════════════════
# RESULT VALUE OBJECTS
# Returned by the service; carry domain decisions to the caller.
# ══════════════════════════════════════════════════════════

class AuthenticationResult:
    """
    Encapsulates the outcome of an authentication attempt.
    Carries all domain objects produced during the flow so the
    application layer can persist them in one transaction.
    """

    def __init__(
        self,
        *,
        succeeded: bool,
        blocked: bool,
        reason: Optional[str],
        session: Optional[Session],
        device: Optional[DeviceFingerprint],
        activity: LoginActivity,
        user: Optional[User],
    ) -> None:
        self.succeeded = succeeded
        self.was_blocked = blocked
        self.reason = reason
        self.session = session
        self.device = device
        self.activity = activity
        self.user = user

    @classmethod
    def success(
        cls,
        session: Session,
        activity: LoginActivity,
        user: User,
        device: Optional[DeviceFingerprint] = None,
    ) -> "AuthenticationResult":
        return cls(
            succeeded=True,
            blocked=False,
            reason=None,
            session=session,
            device=device,
            activity=activity,
            user=user,
        )

    @classmethod
    def failed(
        cls,
        activity: LoginActivity,
        reason: str,
        user: Optional[User] = None,
    ) -> "AuthenticationResult":
        return cls(
            succeeded=False,
            blocked=False,
            reason=reason,
            session=None,
            device=None,
            activity=activity,
            user=user,
        )

    @classmethod
    def blocked(
        cls,
        activity: LoginActivity,
        reason: str,
    ) -> "AuthenticationResult":
        return cls(
            succeeded=False,
            blocked=True,
            reason=reason,
            session=None,
            device=None,
            activity=activity,
            user=None,
        )

    def __repr__(self) -> str:
        state = "SUCCESS" if self.succeeded else ("BLOCKED" if self.was_blocked else "FAILURE")
        return f"<AuthenticationResult outcome={state} reason={self.reason!r}>"


class SessionValidationResult:
    """Lightweight result for session validation checks."""

    def __init__(self, valid: bool, reason: Optional[str] = None) -> None:
        self.valid = valid
        self.reason = reason

    def __bool__(self) -> bool:
        return self.valid

    def __repr__(self) -> str:
        return f"<SessionValidationResult valid={self.valid} reason={self.reason!r}>"