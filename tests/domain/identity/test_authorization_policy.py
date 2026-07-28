import uuid

import pytest

from domain.identity.account import UserRole
from domain.identity.authorization import (
    Permission,
    RoleAssignmentContext,
    RoleAssignmentDenied,
    RoleAssignmentPolicy,
    RoleAssignmentRequiresActor,
    RoleCannotBeSelfAssigned,
    permissions_for_role,
)


def _context(**overrides):
    values = {
        "target_user_id": uuid.uuid4(),
        "current_role": UserRole.PLANNER,
        "new_role": UserRole.VENDOR,
        "actor_user_id": uuid.uuid4(),
        "actor_role": UserRole.ADMIN,
        "permissions": None,
    }
    values.update(overrides)
    return RoleAssignmentContext.for_actor(**values)


def test_admin_role_grants_role_assignment_permissions():
    assert Permission.ASSIGN_USER_ROLE in permissions_for_role(UserRole.ADMIN)
    assert Permission.ASSIGN_ADMIN_ROLE in permissions_for_role(UserRole.ADMIN)
    assert permissions_for_role(UserRole.PLANNER) == frozenset()


def test_policy_allows_admin_to_assign_non_admin_role():
    RoleAssignmentPolicy().ensure_can_assign(_context())


def test_policy_requires_actor_for_role_transition():
    with pytest.raises(RoleAssignmentRequiresActor):
        RoleAssignmentPolicy().ensure_can_assign(
            _context(actor_user_id=None, actor_role=None)
        )


def test_policy_denies_self_assignment_to_admin():
    user_id = uuid.uuid4()
    with pytest.raises(RoleCannotBeSelfAssigned):
        RoleAssignmentPolicy().ensure_can_assign(
            _context(
                target_user_id=user_id,
                new_role=UserRole.ADMIN,
                actor_user_id=user_id,
                actor_role=UserRole.ADMIN,
            )
        )


def test_policy_requires_admin_assignment_permission_for_escalation():
    with pytest.raises(RoleAssignmentDenied):
        RoleAssignmentPolicy().ensure_can_assign(
            _context(
                new_role=UserRole.ADMIN,
                permissions={Permission.ASSIGN_USER_ROLE},
            )
        )
