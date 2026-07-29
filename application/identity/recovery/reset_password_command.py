"""Command for completing password reset."""

from dataclasses import dataclass, field
import re

from domain.identity.credentials import PlainPassword


class InvalidPasswordResetTokenInput(ValueError):
    pass


class InvalidSecurityMetadataHash(ValueError):
    pass


@dataclass(frozen=True)
class PasswordResetTokenInput:
    value: str = field(repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.value, str):
            raise InvalidPasswordResetTokenInput("Password reset token must be text")
        normalized = self.value.strip()
        if not normalized:
            raise InvalidPasswordResetTokenInput("Password reset token is required")
        if normalized != self.value:
            raise InvalidPasswordResetTokenInput("Password reset token cannot have leading or trailing whitespace")
        if any(ord(character) < 32 or ord(character) == 127 for character in normalized):
            raise InvalidPasswordResetTokenInput("Password reset token cannot contain control characters")

    def reveal_for_password_reset(self) -> str:
        return self.value

    def __str__(self) -> str:
        return "******"

    def __repr__(self) -> str:
        return "PasswordResetTokenInput(value='******')"


@dataclass(frozen=True)
class SecurityMetadataHash:
    value: str = field(repr=False)

    _HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")

    def __post_init__(self) -> None:
        if not isinstance(self.value, str) or not self._HEX_SHA256.fullmatch(self.value):
            raise InvalidSecurityMetadataHash("Security metadata hash must be a lowercase SHA-256 hex digest")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class ResetPasswordCommand:
    token: PasswordResetTokenInput
    new_password: PlainPassword
    client_ip_hash: SecurityMetadataHash
    user_agent_hash: SecurityMetadataHash


__all__ = [
    "InvalidPasswordResetTokenInput",
    "InvalidSecurityMetadataHash",
    "PasswordResetTokenInput",
    "ResetPasswordCommand",
    "SecurityMetadataHash",
]
