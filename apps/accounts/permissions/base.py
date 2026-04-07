from rest_framework.permissions import BasePermission

class BaseRolePermission(BasePermission):
    """
    Base permission class for role-based access control.
    """
    allowed_roles = []
    message = "You do not have permission to access this resource."

    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            request.user.role in self.allowed_roles
        )