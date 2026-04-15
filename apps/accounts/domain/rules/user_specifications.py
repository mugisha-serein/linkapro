# Business Rules - Domain Specifications
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from apps.accounts.domain.entities.user import User


class Specification(ABC):
    """Base class for business rules/specifications."""

    @abstractmethod
    def is_satisfied_by(self, candidate: Any) -> bool:
        """Check if candidate satisfies the specification."""
        pass

    def __and__(self, other: Specification) -> AndSpecification:
        return AndSpecification(self, other)

    def __or__(self, other: Specification) -> OrSpecification:
        return OrSpecification(self, other)

    def __invert__(self) -> NotSpecification:
        return NotSpecification(self)


class AndSpecification(Specification):
    """Logical AND of two specifications."""

    def __init__(self, left: Specification, right: Specification):
        self.left = left
        self.right = right

    def is_satisfied_by(self, candidate: Any) -> bool:
        return self.left.is_satisfied_by(candidate) and self.right.is_satisfied_by(candidate)


class OrSpecification(Specification):
    """Logical OR of two specifications."""

    def __init__(self, left: Specification, right: Specification):
        self.left = left
        self.right = right

    def is_satisfied_by(self, candidate: Any) -> bool:
        return self.left.is_satisfied_by(candidate) or self.right.is_satisfied_by(candidate)


class NotSpecification(Specification):
    """Logical NOT of a specification."""

    def __init__(self, spec: Specification):
        self.spec = spec

    def is_satisfied_by(self, candidate: Any) -> bool:
        return not self.spec.is_satisfied_by(candidate)


class UserCanLoginSpecification(Specification):
    """Specification: User can attempt login."""

    def is_satisfied_by(self, candidate: User) -> bool:
        return candidate.can_login()


class UserIsActiveSpecification(Specification):
    """Specification: User account is active."""

    def is_satisfied_by(self, candidate: User) -> bool:
        return candidate.is_active


class UserIsVerifiedSpecification(Specification):
    """Specification: User account is verified."""

    def is_satisfied_by(self, candidate: User) -> bool:
        return candidate.is_verified


class UserAccountNotLockedSpecification(Specification):
    """Specification: User account is not locked."""

    def is_satisfied_by(self, candidate: User) -> bool:
        from datetime import datetime
        if candidate.locked_until is None:
            return True
        return candidate.locked_until <= datetime.now()


class UserHasValidRoleSpecification(Specification):
    """Specification: User has a valid role."""

    def is_satisfied_by(self, candidate: User) -> bool:
        return candidate.role in [User.Role.PLANNER, User.Role.VENDOR, User.Role.ADMIN]


class UserShouldBeLockedSpecification(Specification):
    """Specification: User account should be locked due to failed attempts."""

    def is_satisfied_by(self, candidate: User) -> bool:
        return candidate.should_be_locked()


class UserPasswordChangeRequiredSpecification(Specification):
    """Specification: User must change password."""

    def is_satisfied_by(self, candidate: User) -> bool:
        from apps.accounts.domain.services.authentication_service import PasswordPolicyService
        return PasswordPolicyService.should_force_password_change(candidate)