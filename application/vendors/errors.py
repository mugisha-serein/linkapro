from __future__ import annotations


class VendorApplicationError(Exception):
    default_code = "vendor_application_error"
    default_message = "Vendor operation failed."

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        field_errors: dict[str, list[str]] | None = None,
    ) -> None:
        self.code = code or self.default_code
        self.message = message or self.default_message
        self.field_errors = field_errors or {}
        self.errors = self.field_errors
        super().__init__(self.message)


class VendorResourceNotFound(VendorApplicationError):
    default_code = "vendor_resource_not_found"
    default_message = "Vendor resource not found."


class VendorConflict(VendorApplicationError):
    default_code = "vendor_conflict"
    default_message = "Vendor resource has changed."


class DuplicateVendorProfile(VendorApplicationError):
    default_code = "duplicate_vendor_profile"
    default_message = "User already has a vendor profile."


class InvalidVendorCommand(VendorApplicationError):
    default_code = "vendor_command_invalid"
    default_message = "Vendor command is invalid."


class VendorOperationForbidden(VendorApplicationError):
    default_code = "vendor_operation_forbidden"
    default_message = "Vendor operation is not allowed."
