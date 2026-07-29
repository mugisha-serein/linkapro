"""Identity event outbox port."""

from typing import Protocol


class EventOutbox(Protocol):
    def dispatch(self, event) -> None:
        ...


__all__ = ["EventOutbox"]
