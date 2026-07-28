"""Password hash value object."""
from dataclasses import dataclass, field

from domain.identity.shared.secret_value import _contains_control_character, _fingerprint_secret


@dataclass(frozen=True)
class PasswordHash:
    """Hashed password value object. The hash is created by the infrastructure layer."""
    value: str = field(repr=False)

    def __post_init__(self) -> None:
        if not self.value:
            raise ValueError("Password hash cannot be empty")
        if _contains_control_character(self.value):
            raise ValueError("Password hash contains unsafe control characters")

    @property
    def raw_value(self) -> str:
        """Deprecated compatibility accessor; prefer reveal_for_password_verification()."""
        return self.value

    def reveal(self) -> str:
        """Deprecated compatibility accessor; prefer reveal_for_password_verification()."""
        return self.value

    def reveal_for_password_verification(self) -> str:
        return self.value

    def fingerprint(self) -> str:
        return _fingerprint_secret(self.value)

    def __str__(self) -> str:
        return "******"

    def __repr__(self) -> str:
        return "PasswordHash(value='******')"
