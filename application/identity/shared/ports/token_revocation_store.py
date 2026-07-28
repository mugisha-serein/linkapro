"""Token revocation store port for identity application services."""

from typing import Protocol


class ITokenBlacklist(Protocol):
    def is_blacklisted(self, jti: str) -> bool:
        ...

    def blacklist(self, jti: str, ttl: int) -> None:
        ...

    def is_family_blacklisted(self, family_id: str) -> bool:
        ...

    def blacklist_family(self, family_id: str) -> None:
        ...


__all__ = ["ITokenBlacklist"]
