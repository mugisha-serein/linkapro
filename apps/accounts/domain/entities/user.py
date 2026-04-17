# domain/entities/user.py
# Pure Python — no framework, no ORM, no I/O

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional

from domain.value_objects import (
    UserId,
    Email,
    HashedPassword,
    RoleType,
    utc_now,
)
from domain.exceptions.exception import (
    AccountInactiveError,
    AccountLockedError,
    AuthenticationNotAllowedError,
    RoleAlreadyAssignedError,
    RoleNotFoundError,
    UnauthorizedError,
)
from domain.entities.role import Role, UserRole


# ══════════════════════════════════════════════════════════
# SECURITY CONSTANTS
# Defined here in the domain so enforcement is centralised
# and not scattered across application or infrastructure.
# ══════════════════════════════════════════════════════════

MAX_FAILED_ATTEMPTS: int = 5          # lock threshold
LOCK_DURATION_MINUTES: int = 30       # auto-unlock after this period


# ══════════════════════════════════════════════════════════
# USER — AGGREGATE ROOT
# Central authority for all authentication and session
# eligibility decisions.
# ══════════════════════════════════════════════════════════

@dataclass
class User:
    """
    The central aggregate root of the authentication domain.

    Responsibilities:
    - Guards all authentication eligibility decisions.
    - Owns and enforces the failed-attempt / account-lock lifecycle.
    - Owns role assignments (via UserRole associations).
    - Determines session creation eligibility.
    - Never interacts with persistence, I/O, or external services.

    Zero-trust rules:
    - Default state is UNAUTHENTICATED until explicitly checked.
    - Active status must be positive — not merely "not inactive".
    - Locked state is deterministic and rule-based.
    - All role queries return facts, never grants.
    """

    id: UserId
    email: Email
    hashed_password: HashedPassword
    is_active: bool
    is_locked: bool
    failed_attempts: int
    locked_until: Optional[datetime]
    created_at: datetime
    last_login_at: Optional[datetime]
    _roles: List[UserRole] = field(default_factory=list, repr=False)

    # ── Factory ───────────────────────────────────────────

    @classmethod
    def create(
        cls,
        email: Email,
        hashed_password: HashedPassword,
        initial_role: Optional[Role] = None,
    ) -> "User":
        """
        Create a new user in a default-safe, zero-trust state.
        New users:
        - start ACTIVE (awaiting email verification is an app-layer concern)
        - start UNLOCKED
        - have zero failed attempts
        - optionally receive one initial role (default: USER)
        """
        now = utc_now()
        user_id = UserId.generate()
        user = cls(
            id=user_id,
            email=email,
            hashed_password=hashed_password,
            is_active=True,
            is_locked=False,
            failed_attempts=0,
            locked_until=None,
            created_at=now,
            last_login_at=None,
        )
        role = initial_role or Role.user()
        user._roles.append(
            UserRole(user_id=user_id, role=role, granted_at=now)
        )
        return user

    # ══════════════════════════════════════════════════════
    # AUTHENTICATION ELIGIBILITY
    # ══════════════════════════════════════════════════════

    def can_authenticate(self) -> bool:
        """
        Non-raising predicate — safe for guard conditionals.
        Returns True only if ALL of the following hold:
        - account is active
        - account is not locked (or lock has auto-expired)
        """
        if not self.is_active:
            return False
        self._auto_unlock_if_eligible()
        return not self.is_locked

    def assert_can_authenticate(self) -> None:
        """
        Raising guard — call before processing credentials.
        Raises the most specific domain exception for the blocking reason.
        """
        if not self.is_active:
            raise AccountInactiveError(
                f"Account {self.id} is inactive and cannot authenticate."
            )
        self._auto_unlock_if_eligible()
        if self.is_locked:
            raise AccountLockedError(locked_until=self.locked_until)

    # ══════════════════════════════════════════════════════
    # FAILED ATTEMPT TRACKING
    # ══════════════════════════════════════════════════════

    def register_failed_attempt(self) -> None:
        """
        Increment the failed-attempt counter.
        Triggers an account lock if the threshold is reached.
        Always records the attempt regardless of current lock state
        (for audit completeness).
        """
        self.failed_attempts += 1
        if self.failed_attempts >= MAX_FAILED_ATTEMPTS:
            self.lock_account()

    def reset_failed_attempts(self) -> None:
        """
        Reset the counter on successful authentication.
        Does NOT affect locked/unlocked status —
        unlock must be explicit.
        """
        self.failed_attempts = 0

    # ══════════════════════════════════════════════════════
    # ACCOUNT LOCK / UNLOCK
    # ══════════════════════════════════════════════════════

    def lock_account(self) -> None:
        """
        Lock this account for LOCK_DURATION_MINUTES.
        Idempotent: re-locking resets the lock window.
        """
        self.is_locked = True
        self.locked_until = utc_now() + timedelta(minutes=LOCK_DURATION_MINUTES)

    def unlock_account(self) -> None:
        """
        Explicitly unlock the account (admin or verified recovery action).
        Also resets the failed-attempt counter.
        """
        self.is_locked = False
        self.locked_until = None
        self.failed_attempts = 0

    def _auto_unlock_if_eligible(self) -> None:
        """
        Internal: transparently lift a time-based lock that has elapsed.
        Called before every eligibility check — no external trigger needed.
        """
        if (
            self.is_locked
            and self.locked_until is not None
            and utc_now() >= self.locked_until
        ):
            self.unlock_account()

    # ══════════════════════════════════════════════════════
    # SESSION ELIGIBILITY
    # ══════════════════════════════════════════════════════

    def can_create_session(self) -> bool:
        """
        Determines whether the domain permits session creation.
        Stricter than can_authenticate: active + unlocked required.
        Subclasses or future extensions may layer MFA checks here.
        """
        return self.can_authenticate()

    def record_successful_login(self) -> None:
        """
        Call after a session is successfully created.
        Resets failure counter and updates last-login timestamp.
        """
        self.reset_failed_attempts()
        self.last_login_at = utc_now()

    # ══════════════════════════════════════════════════════
    # ROLE MANAGEMENT
    # ══════════════════════════════════════════════════════

    @property
    def roles(self) -> List[UserRole]:
        """All active role assignments for this user."""
        return [ur for ur in self._roles if ur.is_active]

    @property
    def role_types(self) -> List[RoleType]:
        """Convenience: active role types as a flat list."""
        return [ur.role_type for ur in self.roles]

    def assign_role(
        self,
        role: Role,
        granted_by: Optional[UserId] = None,
    ) -> UserRole:
        """
        Attach a new role to this user.
        Raises RoleAlreadyAssignedError if the user already holds it
        (prevents duplicate, conflicting, or escalation-style re-grants).
        """
        if self.has_role(role.role_type):
            raise RoleAlreadyAssignedError(
                f"User {self.id} already holds the '{role.role_type.value}' role."
            )
        user_role = UserRole(
            user_id=self.id,
            role=role,
            granted_at=utc_now(),
            granted_by=granted_by,
        )
        self._roles.append(user_role)
        return user_role

    def has_role(self, role_type: RoleType) -> bool:
        """Return True if the user actively holds the given role type."""
        return any(ur.role_type == role_type for ur in self.roles)

    def assert_has_role(self, role_type: RoleType) -> None:
        """
        Raising guard for role-gated domain operations.
        Raises UnauthorizedError if the role is absent.
        """
        if not self.has_role(role_type):
            raise UnauthorizedError(
                f"User {self.id} does not hold the '{role_type.value}' role "
                "required for this operation."
            )

    def remove_role(self, role_type: RoleType) -> None:
        """
        Soft-revoke a role assignment.
        Raises RoleNotFoundError if the role is not currently held.
        """
        for ur in self._roles:
            if ur.role_type == role_type and ur.is_active:
                ur.revoke()
                return
        raise RoleNotFoundError(
            f"User {self.id} does not hold an active '{role_type.value}' role."
        )

    # ── Identity ──────────────────────────────────────────

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, User):
            return NotImplemented
        return self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)

    def __repr__(self) -> str:
        return (
            f"<User id={self.id} "
            f"email={self.email} "
            f"active={self.is_active} "
            f"locked={self.is_locked} "
            f"roles={[r.value for r in self.role_types]}>"
        )