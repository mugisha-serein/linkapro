from __future__ import annotations

from datetime import date, datetime, timezone
import uuid

import pytest

from application.vendors.commands import SendInquiryCommand
from application.vendors.errors import InvalidVendorCommand


class DateSubclass(date):
    pass


def _command(*, event_date):
    return SendInquiryCommand(
        vendor_id=uuid.uuid4(),
        requester_id=uuid.uuid4(),
        client_name="Planner",
        client_email="planner@example.com",
        message="Can you support our event?",
        idempotency_key="send-inquiry-event-date",
        event_date=event_date,
    )


@pytest.mark.parametrize("event_date", [None, date(2026, 7, 9)])
def test_send_inquiry_event_date_accepts_only_none_or_exact_date(event_date):
    command = _command(event_date=event_date)

    assert command.event_date is event_date


@pytest.mark.parametrize(
    "invalid_value",
    [
        datetime(2026, 7, 9, 12, 30),
        datetime(2026, 7, 9, 12, 30, tzinfo=timezone.utc),
        "2026-07-09",
        20260709,
        0,
        False,
        12.5,
        [],
        {},
        object(),
        DateSubclass(2026, 7, 9),
    ],
)
def test_send_inquiry_event_date_rejects_datetime_and_all_other_types_with_stable_field_error(
    invalid_value,
):
    with pytest.raises(InvalidVendorCommand) as exc_info:
        _command(event_date=invalid_value)

    assert exc_info.value.code == "vendor_command_invalid"
    assert exc_info.value.field_errors == {
        "event_date": ["Must be a date or null."]
    }
