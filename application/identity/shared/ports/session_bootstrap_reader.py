"""Session bootstrap-claims read port."""

from typing import Protocol


class SessionBootstrapReader(Protocol):
    def get_bootstrap_claims(self, user_id, session_id: str | None = None) -> dict | None:
        ...


__all__ = ["SessionBootstrapReader"]
