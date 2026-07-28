"""Identity authorization domain model."""
from .authorization_errors import (
    AuthorizationError,
    RoleAssignmentDenied,
    RoleAssignmentRequiresActor,
    RoleCannotBeSelfAssigned,
)
from .authorization_events import UserRoleChanged
from .permission import Permission
from .role_assignment_policy import RoleAssignmentContext, RoleAssignmentPolicy
from .role_permissions import ROLE_PERMISSIONS, permissions_for_role

__all__ = [
    "AuthorizationError",
    "Permission",
    "ROLE_PERMISSIONS",
    "RoleAssignmentContext",
    "RoleAssignmentDenied",
    "RoleAssignmentPolicy",
    "RoleAssignmentRequiresActor",
    "RoleCannotBeSelfAssigned",
    "UserRoleChanged",
    "permissions_for_role",
]
