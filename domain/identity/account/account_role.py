"""Identity account roles."""
from enum import Enum


class UserRole(str, Enum):
    PLANNER = "planner"
    VENDOR = "vendor"
    ADMIN = "admin"

    @classmethod
    def public_registration_roles(cls) -> tuple["UserRole", ...]:
        return (cls.PLANNER, cls.VENDOR)

    def can_self_register(self) -> bool:
        return self in self.public_registration_roles()


AccountRole = UserRole


__all__ = ["AccountRole", "UserRole"]
