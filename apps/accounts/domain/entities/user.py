# Domain Entity - Pure Business Logic
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from apps.accounts.domain.value_objects.email import Email
from apps.accounts.domain.value_objects.password import Password


@dataclass(frozen=True)
class User:
    """
    User domain entity.

    Represents a user in the business domain with all business rules and invariants.
    This is a pure business object with no infrastructure concerns.
    """

    class Role:
        PLANNER = "PLANNER"
        VENDOR = "VENDOR"
        ADMIN = "ADMIN"

    email: Email
    role: str
    id: UUID = field(default_factory=uuid4)
    is_active: bool = True
    is_verified: bool = False
    failed_login_count: int = 0
    locked_until: Optional[datetime] = None
    last_password_change_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        """Validate business invariants."""
        self._validate_role()
        self._validate_failed_login_count()

    def _validate_role(self) -> None:
        """Ensure role is valid."""
        if self.role not in [self.Role.PLANNER, self.Role.VENDOR, self.Role.ADMIN]:
            raise ValueError(f"Invalid role: {self.role}")

    def _validate_failed_login_count(self) -> None:
        """Ensure failed login count is non-negative."""
        if self.failed_login_count < 0:
            raise ValueError("Failed login count cannot be negative")

    def can_login(self) -> bool:
        """Business rule: Determine if user can attempt login."""
        if not self.is_active:
            return False

        if self.locked_until and self.locked_until > datetime.now():
            return False

        return True

    def should_be_locked(self, max_failed_attempts: int = 5) -> bool:
        """Business rule: Determine if account should be locked."""
        return self.failed_login_count >= max_failed_attempts

    def record_failed_login(self) -> User:
        """Business logic: Record a failed login attempt."""
        new_failed_count = self.failed_login_count + 1
        locked_until = None

        # Lock account after 5 failed attempts for 30 minutes
        if new_failed_count >= 5:
            locked_until = datetime.now().replace(minute=datetime.now().minute + 30)

        return User(
            id=self.id,
            email=self.email,
            role=self.role,
            is_active=self.is_active,
            is_verified=self.is_verified,
            failed_login_count=new_failed_count,
            locked_until=locked_until,
            last_password_change_at=self.last_password_change_at,
            created_at=self.created_at,
            updated_at=datetime.now(),
        )

    def record_successful_login(self) -> User:
        """Business logic: Record a successful login."""
        return User(
            id=self.id,
            email=self.email,
            role=self.role,
            is_active=self.is_active,
            is_verified=self.is_verified,
            failed_login_count=0,  # Reset failed attempts
            locked_until=None,  # Clear lock
            last_password_change_at=self.last_password_change_at,
            created_at=self.created_at,
            updated_at=datetime.now(),
        )

    def change_password(self, new_password: Password) -> User:
        """Business logic: Change user password."""
        return User(
            id=self.id,
            email=self.email,
            role=self.role,
            is_active=self.is_active,
            is_verified=self.is_verified,
            failed_login_count=self.failed_login_count,
            locked_until=self.locked_until,
            last_password_change_at=datetime.now(),
            created_at=self.created_at,
            updated_at=datetime.now(),
        )

    def verify_account(self) -> User:
        """Business logic: Mark account as verified."""
        return User(
            id=self.id,
            email=self.email,
            role=self.role,
            is_active=self.is_active,
            is_verified=True,
            failed_login_count=self.failed_login_count,
            locked_until=self.locked_until,
            last_password_change_at=self.last_password_change_at,
            created_at=self.created_at,
            updated_at=datetime.now(),
        )

    def change_role(self, new_role: str) -> User:
        """Business logic: Change user role."""
        # Validate the new role
        if new_role not in [self.Role.PLANNER, self.Role.VENDOR, self.Role.ADMIN]:
            raise ValueError(f"Invalid role: {new_role}")

        return User(
            id=self.id,
            email=self.email,
            role=new_role,
            is_active=self.is_active,
            is_verified=self.is_verified,
            failed_login_count=self.failed_login_count,
            locked_until=self.locked_until,
            last_password_change_at=self.last_password_change_at,
            created_at=self.created_at,
            updated_at=datetime.now(),
        )