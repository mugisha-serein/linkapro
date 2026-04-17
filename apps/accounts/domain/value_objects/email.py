import re
from dataclasses import dataclass

from domain.exceptions import InvalidEmailError


@dataclass(frozen=True)
class Email:
    """
    Value object representing a validated, normalized email address.

    Immutable. Equality is structural (same address = same identity).
    Normalization: lowercased, whitespace stripped.
    """

    address: str

    # Minimal RFC-5321-inspired pattern. Deliberate: domain layer
    # does not need a full RFC 5322 parser.
    _PATTERN: str = r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"

    def __post_init__(self) -> None:
        normalized = self.address.strip().lower()
        # frozen=True means we must use object.__setattr__ to set derived values
        object.__setattr__(self, "address", normalized)

        if not re.match(self._PATTERN, normalized):
            raise InvalidEmailError(
                f"'{self.address}' is not a valid email address."
            )

    def __str__(self) -> str:
        return self.address

    def domain_part(self) -> str:
        return self.address.split("@")[1]
