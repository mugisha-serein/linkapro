"""Unit-of-work port for identity multi-write application flows."""

from __future__ import annotations

from typing import Protocol, Self


class IdentityUnitOfWork(Protocol):
    def __enter__(self) -> Self:
        ...

    def __exit__(self, exc_type, exc, traceback) -> bool | None:
        ...

    def commit(self) -> None:
        ...

    def rollback(self) -> None:
        ...


class NullIdentityUnitOfWork:
    def __enter__(self) -> "NullIdentityUnitOfWork":
        return self

    def __exit__(self, exc_type, exc, traceback) -> bool | None:
        return None

    def commit(self) -> None:
        return None

    def rollback(self) -> None:
        return None


__all__ = ["IdentityUnitOfWork", "NullIdentityUnitOfWork"]
