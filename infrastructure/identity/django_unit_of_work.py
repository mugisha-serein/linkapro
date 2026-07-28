"""Django transaction-backed identity unit of work."""

from __future__ import annotations

from django.db import transaction

from application.identity.shared.ports import IdentityUnitOfWork


class DjangoIdentityUnitOfWork(IdentityUnitOfWork):
    def __init__(self) -> None:
        self._atomic = None
        self._committed = False

    def __enter__(self) -> "DjangoIdentityUnitOfWork":
        self._committed = False
        self._atomic = transaction.atomic()
        self._atomic.__enter__()
        return self

    def __exit__(self, exc_type, exc, traceback) -> bool | None:
        if self._atomic is None:
            return None
        if exc_type is not None or not self._committed:
            transaction.set_rollback(True)
        return self._atomic.__exit__(exc_type, exc, traceback)

    def commit(self) -> None:
        self._committed = True

    def rollback(self) -> None:
        self._committed = False
        transaction.set_rollback(True)


__all__ = ["DjangoIdentityUnitOfWork"]
