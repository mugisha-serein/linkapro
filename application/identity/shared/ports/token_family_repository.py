"""Token-family revocation port for identity session use cases."""

from typing import Protocol


class TokenFamilyRepository(Protocol):
    def blacklist_family(self, family_id: str) -> None:
        ...


__all__ = ["TokenFamilyRepository"]
