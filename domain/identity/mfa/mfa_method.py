"""MFA method identifiers."""
from enum import Enum


class MfaMethod(str, Enum):
    TOTP = "totp"
    RECOVERY_CODE = "recovery_code"
