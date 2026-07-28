"""Refresh token family model."""
from __future__ import annotations

from dataclasses import dataclass
import uuid


@dataclass(frozen=True)
class RotatedTokenIds:
    access_jti: str
    refresh_jti: str


@dataclass(frozen=True)
class TokenFamily:
    id: str
    revoked: bool = False

    def __post_init__(self) -> None:
        if not self.id or not str(self.id).strip():
            raise ValueError("Token family id cannot be empty")
        object.__setattr__(self, "id", str(self.id))

    @classmethod
    def issue(cls) -> "TokenFamily":
        return cls(id=str(uuid.uuid4()))

    def revoke(self) -> "TokenFamily":
        return TokenFamily(id=self.id, revoked=True)

    def detect_replay(self, *, token_already_used: bool) -> bool:
        return bool(token_already_used)

    def next_token_id(self) -> str:
        return str(uuid.uuid4())

    def rotate(self) -> RotatedTokenIds:
        return RotatedTokenIds(
            access_jti=self.next_token_id(),
            refresh_jti=self.next_token_id(),
        )


__all__ = ["RotatedTokenIds", "TokenFamily"]
