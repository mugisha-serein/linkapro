"""Role assignment policy."""
from __future__ import annotations

from dataclasses import dataclass
import uuid
from typing import Iterable

from domain.identity.account import UserRole

from .authorization_errors import RoleAssignmentDenied, RoleAssignmentRequiresActor, RoleCannotBeSelfAssigned
from .permission import Permission
from .role_permissions import permissions_for_role


_ROLE_RANK: dict[UserRole, int] = {
    UserRole.PLANNER: 1,
    UserRole.VENDOR: 1,
    UserRole.ADMIN: 2,
}


@dataclass(frozen=True)
class RoleAssignmentContext:
    target_user_id: uuid.UUID
    current_role: UserRole
    new_role: UserRole
    actor_user_id: uuid.UUID | None
    actor_role: UserRole | None
    permissions: frozenset[Permission]

    @classmethod
    def for_actor(
        cls,
        *,
        target_user_id: uuid.UUID,
        current_role: UserRole | str,
        new_role: UserRole | str,
        actor_user_id: uuid.UUID | None,
        actor_role: UserRole | str | None,
        permissions: Iterable[Permission | str] | None = None,
    ) -> "RoleAssignmentContext":
        normalized_actor_role = UserRole(actor_role) if actor_role is not None else None
        if permissions is None and normalized_actor_role is not None:
            normalized_permissions = permissions_for_role(normalized_actor_role)
        else:
            normalized_permissions = frozenset(Permission(permission) for permission in (permissions or ()))
        return cls(
            target_user_id=target_user_id,
            current_role=UserRole(current_role),
            new_role=UserRole(new_role),
            actor_user_id=actor_user_id,
            actor_role=normalized_actor_role,
            permissions=normalized_permissions,
        )


class RoleAssignmentPolicy:
    def ensure_can_assign(self, context: RoleAssignmentContext) -> None:
        if context.actor_user_id is None or context.actor_role is None:
            raise RoleAssignmentRequiresActor("Role assignment requires an authorizing actor")
        if Permission.ASSIGN_USER_ROLE not in context.permissions:
            raise RoleAssignmentDenied("Role assignment requires user role assignment permission")
        if context.new_role == context.current_role:
            return
        if context.actor_user_id == context.target_user_id and context.new_role is UserRole.ADMIN:
            raise RoleCannotBeSelfAssigned("Users cannot assign themselves the admin role")
        if self._is_privilege_escalation(context) and Permission.ASSIGN_ADMIN_ROLE not in context.permissions:
            raise RoleAssignmentDenied("Privilege escalation requires admin role assignment permission")

    @staticmethod
    def _is_privilege_escalation(context: RoleAssignmentContext) -> bool:
        return _ROLE_RANK[context.new_role] > _ROLE_RANK[context.current_role]
