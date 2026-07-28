"""Security reason value object."""
from dataclasses import dataclass
from typing import ClassVar


class InvalidSecurityReasonError(ValueError):
    pass


@dataclass(frozen=True)
class SecurityReason:
    """Human-readable security context that must not carry secrets."""
    value: str

    _FORBIDDEN_FRAGMENTS: ClassVar[tuple[str, ...]] = (
        "password",
        "token",
        "secret",
        "totp",
        "refresh",
    )

    def __post_init__(self) -> None:
        normalized = self.value.strip()
        if not normalized:
            raise InvalidSecurityReasonError("Security reason cannot be empty")
        lowered = normalized.lower()
        if any(fragment in lowered for fragment in self._FORBIDDEN_FRAGMENTS):
            raise InvalidSecurityReasonError("Security reason cannot contain secret-like text")
        object.__setattr__(self, "value", normalized)

    def __str__(self) -> str:
        return self.value
