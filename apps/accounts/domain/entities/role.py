# domain/entities/role.py
# Pure Python — no framework, no ORM, no I/O

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from domain.value_objects import RoleType, UserId, utc_now
from domain.exceptions import RoleAlreadyAssignedError, RoleNotFoundError


# ══════════════════════════════════════════════════════════
# ROLE ENTITY
# A pure capability descriptor.  No business logic of its own —
# it exists only to be assigned to, and read from, a User.
# ══════════════════════════════════════════════════════════

@dataclass
class Role:
    """
    Represents a named capability group within the marketplace.

    Rules:
    - Carries only the RoleType label and an optional description.
    - Makes no decisions; only serves as a fact to be evaluated elsewhere.
    - Equality is by role_type (one canonical Role per RoleType exists).
    """

    role_type: RoleType
    description: str = ""

    # ── Equality & hashing by value ──────────────────────
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Role):
            return NotImplemented
        return self.role_type == other.role_type

    def __hash__(self) -> int:
        return hash(self.role_type)

    def __repr__(self) -> str:
        return f"<Role type={self.role_type.value}>"

    # ── Factory helpers ───────────────────────────────────
    @classmethod
    def user(cls) -> "Role":
        return cls(role_type=RoleType.USER, description="Standard marketplace buyer.")

    @classmethod
    def vendor(cls) -> "Role":
        return cls(role_type=RoleType.VENDOR, description="Approved seller account.")

    @classmethod
    def admin(cls) -> "Role":
        return cls(role_type=RoleType.ADMIN, description="Platform administrator.")


# ══════════════════════════════════════════════════════════
# USER ROLE ASSOCIATION ENTITY
# Links a User to a Role.
# Enforces: no duplicate assignments, tracks assignment metadata.
# ══════════════════════════════════════════════════════════

@dataclass
class UserRole:
    """
    Association entity between a User and a Role.

    Rules:
    - A user cannot hold the same RoleType more than once (enforced by
      the User aggregate, but UserRole is immutable once created).
    - Records who granted the role and when (for audit).
    - The 'is_active' flag supports soft-revocation without deletion.
    """

    user_id: UserId
    role: Role
    granted_at: datetime = field(default_factory=utc_now)
    granted_by: Optional[UserId] = None   # None = system/self-assigned
    is_active: bool = True

    # ── Identity ──────────────────────────────────────────
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, UserRole):
            return NotImplemented
        return (self.user_id == other.user_id
                and self.role.role_type == other.role.role_type)

    def __hash__(self) -> int:
        return hash((self.user_id, self.role.role_type))

    def __repr__(self) -> str:
        return (
            f"<UserRole user={self.user_id} "
            f"role={self.role.role_type.value} "
            f"active={self.is_active}>"
        )

    # ── Behaviour ─────────────────────────────────────────
    @property
    def role_type(self) -> RoleType:
        return self.role.role_type

    def revoke(self) -> None:
        """Soft-revoke this role assignment."""
        self.is_active = False