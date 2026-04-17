from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from domain.entities.role import Role
from domain.exceptions import RoleAlreadyAssignedError, RoleNotFoundError
from domain.value_objects.role_type import RoleType


@dataclass
class UserRole:
    """
    Association entity linking a User to a set of Roles.

    Responsibilities:
    - Enforce no duplicate role assignments
    - Support multiple roles per user
    - Track assignment timestamps for audit purposes

    This entity does NOT make authorization decisions.
    Authorization decisions live in the authorization service.
    """

    user_id: UUID
    _assignments: dict[RoleType, tuple[Role, datetime]] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self._assignments is None:
            self._assignments = {}

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    def assign_role(self, role: Role) -> None:
        """
        Assign a role to the user.

        Raises RoleAlreadyAssignedError if the role is already present.
        Idempotent in intent but strict in contract — callers must check
        before assigning if they want silent no-ops.
        """
        if role.role_type in self._assignments:
            raise RoleAlreadyAssignedError(
                f"Role '{role.role_type.value}' is already assigned to user {self.user_id}."
            )
        self._assignments[role.role_type] = (role, datetime.now(timezone.utc))

    def remove_role(self, role_type: RoleType) -> None:
        """
        Remove a role from the user.

        Raises RoleNotFoundError if the role is not currently assigned.
        """
        if role_type not in self._assignments:
            raise RoleNotFoundError(
                f"Role '{role_type.value}' is not assigned to user {self.user_id}."
            )
        del self._assignments[role_type]

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def has_role(self, role_type: RoleType) -> bool:
        """Return True if the given role type is currently assigned."""
        return role_type in self._assignments

    def all_role_types(self) -> list[RoleType]:
        return list(self._assignments.keys())

    def assigned_at(self, role_type: RoleType) -> datetime | None:
        """Return the UTC timestamp when a role was assigned, or None."""
        entry = self._assignments.get(role_type)
        return entry[1] if entry else None
