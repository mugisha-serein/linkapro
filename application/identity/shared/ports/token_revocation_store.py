"""Token revocation store port for identity application services."""

from typing import Protocol

from application.identity.shared.dtos import MfaLoginGrant


class TokenRevocationStore(Protocol):
    def is_blacklisted(self, jti: str) -> bool:
        ...

    def blacklist(self, jti: str, ttl: int) -> None:
        ...

    def is_family_blacklisted(self, family_id: str) -> bool:
        ...

    def blacklist_family(self, family_id: str) -> None:
        ...

    def is_mfa_grant_blacklisted(self, grant: MfaLoginGrant) -> bool:
        ...

    def blacklist_mfa_grant(self, grant: MfaLoginGrant) -> None:
        ...


__all__ = ["TokenRevocationStore"]
