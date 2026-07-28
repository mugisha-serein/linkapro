"""Person name value object."""
from dataclasses import dataclass


@dataclass(frozen=True)
class PersonName:
    """Person name used by the identity domain."""
    first_name: str
    last_name: str

    def __post_init__(self) -> None:
        first_name = self.first_name.strip()
        last_name = self.last_name.strip()
        if not first_name:
            raise ValueError("First name cannot be empty")
        if not last_name:
            raise ValueError("Last name cannot be empty")
        object.__setattr__(self, "first_name", first_name)
        object.__setattr__(self, "last_name", last_name)

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"
