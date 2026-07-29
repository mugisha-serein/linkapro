from rest_framework.permissions import BasePermission


class IsPlanner(BasePermission):
    message = "Planner access required."

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        return bool(user and user.is_authenticated and getattr(user, "role", None) == "planner")


class IsVendor(BasePermission):
    message = "Vendor access required."

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        return bool(user and user.is_authenticated and getattr(user, "role", None) == "vendor")


class IsAdmin(BasePermission):
    message = "Admin access required."

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        return bool(user and user.is_authenticated and getattr(user, "role", None) == "admin")
