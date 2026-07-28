"""Compatibility imports for identity password reset use cases."""

from application.identity.recovery.reset_password import (
    PasswordResetGateway,
    PasswordResetResult,
    PasswordResetVerification,
    ResetPasswordCommandHandler,
)

__all__ = [
    "PasswordResetGateway",
    "PasswordResetResult",
    "PasswordResetVerification",
    "ResetPasswordCommandHandler",
]
