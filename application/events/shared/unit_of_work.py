from typing import Callable, Protocol, TypeVar

T = TypeVar("T")


class EventUnitOfWork(Protocol):
    """Current event handlers use direct repository calls with no UoW.

    This protocol captures the smallest transaction boundary needed for future
    wiring without changing today's handler behavior.
    """

    def execute(self, operation: Callable[[], T]) -> T: ...
