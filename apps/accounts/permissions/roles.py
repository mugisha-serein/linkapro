from .base import BaseRolePermission
from ..models import User

class IsPlannerUser(BaseRolePermission):
    """
    Allows access only to Planner users.
    """
    allowed_roles = [User.Roles.PLANNER]
    message = "Only planner users can access this resource."


class IsVendorUser(BaseRolePermission):
    """
    Allows access only to Vendor users.
    """
    allowed_roles = [User.Roles.VENDOR]
    message = "Only vendor users can access this resource."


class IsAdminUser(BaseRolePermission):
    """
    Allows access only to Admin users.
    """
    allowed_roles = [User.Roles.ADMIN]
    message = "Only admin users can access this resource."


class IsPlannerOrAdmin(BaseRolePermission):
    """
    Allows access to Planner or Admin users.
    """
    allowed_roles = [User.Roles.PLANNER, User.Roles.ADMIN]
    message = "Only planner or admin users can access this resource."


class IsVendorOrAdmin(BaseRolePermission):
    """
    Allows access to Vendor or Admin users.
    """
    allowed_roles = [User.Roles.VENDOR, User.Roles.ADMIN]
    message = "Only vendor or admin users can access this resource."


class IsApprovedVendor(BaseRolePermission):
    """
    Allows access only to approved Vendor users.
    """
    allowed_roles = [User.Roles.VENDOR]
    message = "Only approved vendor users can access this resource."

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        
        # Check if vendor profile is approved
        vendor_profile = getattr(request.user, 'vendor_profile', None)
        if not vendor_profile:
            return False
        
        return vendor_profile.approval_status == vendor_profile.ApprovalStatus.APPROVED