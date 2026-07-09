from __future__ import annotations

import pytest

from application.vendors.dtos import PageDTO


def test_page_dto_accepts_valid_boundary_values_and_normalizes_next_cursor():
    first_page = PageDTO(
        items=(1,),
        total=1,
        limit=1,
        offset=0,
        next_cursor="  next-page-token  ",
    )
    maximum_page = PageDTO(
        items=tuple(range(100)),
        total=100,
        limit=100,
        offset=10_000,
        next_cursor="x" * 512,
    )
    empty_page = PageDTO(items=(), total=0, limit=50, offset=0)

    assert first_page.next_cursor == "next-page-token"
    assert maximum_page.next_cursor == "x" * 512
    assert empty_page.next_cursor is None


@pytest.mark.parametrize("total", [-1, 1.5, "1", None, True, False])
def test_page_dto_rejects_invalid_total(total):
    with pytest.raises(ValueError, match="Page total must be a nonnegative integer"):
        PageDTO(items=(), total=total, limit=10, offset=0)


@pytest.mark.parametrize("limit", [0, 101, -1])
def test_page_dto_rejects_limit_outside_existing_bounds(limit):
    with pytest.raises(ValueError, match="Page limit must be between 1 and 100"):
        PageDTO(items=(), total=0, limit=limit, offset=0)


@pytest.mark.parametrize("limit", [1.5, "10", None, True, False])
def test_page_dto_rejects_non_integer_limit(limit):
    with pytest.raises(ValueError, match="Page limit must be an integer"):
        PageDTO(items=(), total=0, limit=limit, offset=0)


@pytest.mark.parametrize("offset", [-1, 10_001])
def test_page_dto_rejects_offset_outside_existing_bounds(offset):
    with pytest.raises(ValueError, match="Page offset must be between 0 and 10000"):
        PageDTO(items=(), total=0, limit=10, offset=offset)


@pytest.mark.parametrize("offset", [1.5, "0", None, True, False])
def test_page_dto_rejects_non_integer_offset(offset):
    with pytest.raises(ValueError, match="Page offset must be an integer"):
        PageDTO(items=(), total=0, limit=10, offset=offset)


def test_page_dto_rejects_more_items_than_limit():
    with pytest.raises(ValueError, match="Page items cannot exceed the page limit"):
        PageDTO(items=(1, 2), total=2, limit=1, offset=0)


def test_page_dto_rejects_total_below_returned_item_count():
    with pytest.raises(
        ValueError,
        match="Page total cannot be less than the number of items",
    ):
        PageDTO(items=(1, 2), total=1, limit=2, offset=0)


@pytest.mark.parametrize(
    ("next_cursor", "message"),
    [
        (123, "Page next_cursor must be a string"),
        ("", "Page next_cursor cannot be blank"),
        ("   ", "Page next_cursor cannot be blank"),
        ("x" * 513, "Page next_cursor must be 512 characters or fewer"),
    ],
)
def test_page_dto_rejects_invalid_next_cursor(next_cursor, message):
    with pytest.raises(ValueError, match=message):
        PageDTO(
            items=(),
            total=0,
            limit=10,
            offset=0,
            next_cursor=next_cursor,
        )
