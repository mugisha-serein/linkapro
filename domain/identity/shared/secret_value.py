"""Sensitive string value object helpers."""
import hashlib
from dataclasses import dataclass, field


def _contains_control_character(value: str) -> bool:
    return any(ord(character) < 32 or ord(character) == 127 for character in value)


def _fingerprint_secret(value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return f"sha256:{digest[:12]}"


@dataclass(frozen=True)
class SecretValue:
    """Sensitive string value that is safe by default in logs and reprs."""
    value: str = field(repr=False)

    def __post_init__(self) -> None:
        if not self.value or not self.value.strip():
            raise ValueError("Secret value cannot be empty")
        if _contains_control_character(self.value):
            raise ValueError("Secret value contains unsafe control characters")

    @property
    def raw_value(self) -> str:
        """Deprecated compatibility accessor; prefer purpose-specific reveal methods."""
        return self.value

    def reveal(self) -> str:
        """Deprecated compatibility accessor; prefer purpose-specific reveal methods."""
        return self.value

    def fingerprint(self) -> str:
        return _fingerprint_secret(self.value)

    def __str__(self) -> str:
        return "******"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(value='******')"
