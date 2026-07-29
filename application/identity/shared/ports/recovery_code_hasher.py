"""Recovery-code hashing port."""

from typing import Protocol


class RecoveryCodeHasher(Protocol):
    def hash_recovery_code(self, code: str) -> str:
        ...


__all__ = ["RecoveryCodeHasher"]
