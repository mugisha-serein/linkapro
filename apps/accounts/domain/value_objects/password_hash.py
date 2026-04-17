from dataclasses import dataclass

from domain.exceptions import InvalidValueError


@dataclass(frozen=True)
class PasswordHash:
    """
    Value object wrapping a pre-hashed password string.

    The domain layer NEVER handles plaintext passwords or performs hashing.
    Hashing is an infrastructure concern. This value object only carries
    the result and enforces it is non-empty and structurally present.

    Zero-trust rule: the hash is never exposed raw in equality checks
    intended for authentication — credential verification is delegated
    to infrastructure. Here we only store and transport the hash safely.
    """

    value: str

    def __post_init__(self) -> None:
        if not self.value or not self.value.strip():
            raise InvalidValueError("Password hash cannot be empty.")

    def __repr__(self) -> str:
        # Never leak the hash in logs or repr output.
        return "PasswordHash(***)"

    def __str__(self) -> str:
        return "***"
