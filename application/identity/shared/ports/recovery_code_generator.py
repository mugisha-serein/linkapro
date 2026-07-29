"""Recovery-code generation port."""

from typing import Protocol


class RecoveryCodeGenerator(Protocol):
    def generate(self) -> str:
        ...


__all__ = ["RecoveryCodeGenerator"]
