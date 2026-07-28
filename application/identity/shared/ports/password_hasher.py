"""Password hashing port for identity application services."""

from typing import Protocol

from domain.identity.credentials import PasswordHash, PlainPassword


class PasswordHasher(Protocol):
    def hash(self, plain: PlainPassword) -> str:
        ...

    def verify(self, plain: PlainPassword | str, hashed: PasswordHash) -> bool:
        ...

    def verify_against_dummy(self, password: PlainPassword) -> None:
        ...


__all__ = ["PasswordHasher"]
