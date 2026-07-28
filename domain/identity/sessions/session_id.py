"""Session identifier value object."""
from dataclasses import dataclass


@dataclass(frozen=True)
class SessionId:
    value: str

    def __post_init__(self) -> None:
        if not self.value or not str(self.value).strip():
            raise ValueError("Session id cannot be empty")
        object.__setattr__(self, "value", str(self.value))

    def __str__(self) -> str:
        return self.value
