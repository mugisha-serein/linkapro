"""Session security-state read port."""

from typing import Protocol


class SessionSecurityStateReader(Protocol):
    def is_token_revoked_for_user(self, user_id, issued_at) -> bool:
        ...

    def token_version_matches_active_user(self, user_id, token_version) -> bool:
        ...


__all__ = ["SessionSecurityStateReader"]
