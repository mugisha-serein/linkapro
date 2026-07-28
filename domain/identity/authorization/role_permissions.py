"""Permissions granted by identity role."""
from domain.identity.account import UserRole

from .permission import Permission


ROLE_PERMISSIONS: dict[UserRole, frozenset[Permission]] = {
    UserRole.PLANNER: frozenset(),
    UserRole.VENDOR: frozenset(),
    UserRole.ADMIN: frozenset(
        {
            Permission.ASSIGN_USER_ROLE,
            Permission.ASSIGN_ADMIN_ROLE,
        }
    ),
}


def permissions_for_role(role: UserRole | str) -> frozenset[Permission]:
    return ROLE_PERMISSIONS[UserRole(role)]
