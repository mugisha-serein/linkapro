from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")

@dataclass(frozen=True)
class PageRequest:
    limit: int = 50
    offset: int = 0
    cursor: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.limit, int) or isinstance(self.limit, bool):
            raise ValueError("Page limit must be an integer.")
        if not isinstance(self.offset, int) or isinstance(self.offset, bool):
            raise ValueError("Page offset must be an integer.")
        if self.limit < 1 or self.limit > 100:
            raise ValueError("Page limit must be between 1 and 100.")
        if self.offset < 0 or self.offset > 10_000:
            raise ValueError("Page offset must be between 0 and 10000.")
        if self.cursor is not None:
            if not isinstance(self.cursor, str):
                raise ValueError("Page cursor must be a string.")
            cursor = self.cursor.strip()
            if not cursor:
                raise ValueError("Page cursor cannot be blank.")
            if len(cursor) > 512:
                raise ValueError("Page cursor must be 512 characters or fewer.")
            if self.offset != 0:
                raise ValueError("Cursor pagination cannot be combined with a nonzero offset.")
            object.__setattr__(self, "cursor", cursor)

@dataclass(frozen=True)
class Page(Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int
    next_cursor: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.items, list):
            raise ValueError("Page items must be a list.")
        if not isinstance(self.total, int) or isinstance(self.total, bool) or self.total < 0:
            raise ValueError("Page total must be a nonnegative integer.")
        PageRequest(limit=self.limit, offset=self.offset)
        if len(self.items) > self.limit:
            raise ValueError("Page items cannot exceed the page limit.")
        if self.total < len(self.items):
            raise ValueError("Page total cannot be less than the number of items.")
        if self.offset > self.total and self.total != 0:
            raise ValueError("Page offset cannot exceed total.")
        if self.next_cursor is not None:
            if not isinstance(self.next_cursor, str):
                raise ValueError("Page next_cursor must be a string.")
            next_cursor = self.next_cursor.strip()
            if not next_cursor:
                raise ValueError("Page next_cursor cannot be blank.")
            if len(next_cursor) > 512:
                raise ValueError("Page next_cursor must be 512 characters or fewer.")
            object.__setattr__(self, "next_cursor", next_cursor)
