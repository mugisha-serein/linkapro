"""Email address value object."""
import re
from dataclasses import dataclass


class InvalidEmailError(ValueError):
    pass


@dataclass(frozen=True)
class Email:
    """Validated email address value object."""
    value: str

    def __post_init__(self) -> None:
        normalized = self.value.strip().lower()
        object.__setattr__(self, "value", normalized)
        if len(normalized) > 254:
            raise InvalidEmailError("Email is too long")
        if not self._is_valid(normalized):
            raise InvalidEmailError("Invalid email")

    @staticmethod
    def _is_valid(email: str) -> bool:
        pattern = r"^[a-z0-9_.+-]+@[a-z0-9-]+\.[a-z0-9-.]+$"
        return re.match(pattern, email) is not None

    def __str__(self) -> str:
        return self.value
