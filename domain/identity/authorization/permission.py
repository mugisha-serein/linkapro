"""Identity permissions."""
from enum import Enum


class Permission(str, Enum):
    ASSIGN_USER_ROLE = "identity.assign_user_role"
    ASSIGN_ADMIN_ROLE = "identity.assign_admin_role"
