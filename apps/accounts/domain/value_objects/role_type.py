from enum import Enum


class RoleType(str, Enum):
    """
    Defines the set of recognized authorization roles in the platform.

    Roles are ordered by privilege level. Higher ordinal = greater capability.
    No role grants implicit access — all access must be explicitly checked.
    """

    USER = "USER"
    VENDOR = "VENDOR"
    ADMIN = "ADMIN"

    def is_elevated(self) -> bool:
        """True for roles above standard user access."""
        return self in (RoleType.VENDOR, RoleType.ADMIN)

    def is_admin(self) -> bool:
        return self == RoleType.ADMIN
