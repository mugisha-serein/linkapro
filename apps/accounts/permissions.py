from rest_framework.permissions import BasePermission
from .models import User


class IsPlannerUser(BasePermission):
    """
    Allows access only to Planner users.
    """
    message = "Only planner users can access this resource."

    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            request.user.role == User.Roles.PLANNER
        )


class IsVendorUser(BasePermission):
    """
    Allows access only to Vendor users.
    """
    message = "Only vendor users can access this resource."

    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            request.user.role == User.Roles.VENDOR
        )


class IsAdminUser(BasePermission):
    """
    Allows access only to Admin users.
    """
    message = "Only admin users can access this resource."

    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            request.user.role == User.Roles.ADMIN
        )


class IsPlannerOrAdmin(BasePermission):
    """
    Allows access to Planner or Admin users.
    """
    message = "Only planner or admin users can access this resource."

    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            request.user.role in [User.Roles.PLANNER, User.Roles.ADMIN]
        )


class IsVendorOrAdmin(BasePermission):
    """
    Allows access to Vendor or Admin users.
    """
    message = "Only vendor or admin users can access this resource."

    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            request.user.role in [User.Roles.VENDOR, User.Roles.ADMIN]
        )


class IsApprovedVendor(BasePermission):
    """
    Allows access only to approved Vendor users.
    """
    message = "Only approved vendor users can access this resource."

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        
        if request.user.role != User.Roles.VENDOR:
            return False
        
        # Check if vendor profile is approved
        vendor_profile = getattr(request.user, 'vendor_profile', None)
        if not vendor_profile:
            return False
        
        return vendor_profile.approval_status == vendor_profile.ApprovalStatus.APPROVED
