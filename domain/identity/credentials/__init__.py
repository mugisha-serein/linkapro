"""Identity credential value objects."""
from .credentials_events import UserPasswordChanged
from .email_address import Email, InvalidEmailError
from .password_hash import PasswordHash
from .password_history import (
    PasswordHistory,
    PasswordHistoryEntry,
    PasswordReuseError,
    PasswordReuseNotAllowed,
    PasswordVerifier,
)
from .password_policy import PasswordPolicy
from .plain_password import PlainPassword, WeakPasswordError

__all__ = [
    "Email",
    "InvalidEmailError",
    "PasswordHash",
    "PasswordHistory",
    "PasswordHistoryEntry",
    "PasswordPolicy",
    "PasswordReuseError",
    "PasswordReuseNotAllowed",
    "PasswordVerifier",
    "PlainPassword",
    "UserPasswordChanged",
    "WeakPasswordError",
]
