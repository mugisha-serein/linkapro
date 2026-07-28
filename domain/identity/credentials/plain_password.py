"""Plain password value object."""
from dataclasses import dataclass, field

from domain.identity.shared.secret_value import _contains_control_character, _fingerprint_secret


class WeakPasswordError(ValueError):
    pass


@dataclass(frozen=True)
class PlainPassword:
    """Plain-text password used only during registration/password change. Never stored."""
    value: str = field(repr=False)

    def __post_init__(self) -> None:
        if _contains_control_character(self.value):
            raise WeakPasswordError("Password contains unsafe control characters")
        if self.value != self.value.strip():
            raise WeakPasswordError("Password cannot start or end with whitespace")

    def __str__(self) -> str:
        return "******"

    def __repr__(self) -> str:
        return "PlainPassword(value='******')"

    def fingerprint(self) -> str:
        return _fingerprint_secret(self.value)
