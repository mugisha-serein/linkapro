from datetime import date, datetime, timezone

import pytest

from domain.vendors.shared.pagination import PageRequest
from infrastructure.repos.inquiries.django_repository import DjangoInquiryRepository
from tests.factories import create_inquiry, create_vendor_profile

pytestmark = pytest.mark.django_db


def test_inquiry_repository_search_filters_text_status_and_date_range():
    vendor = create_vendor_profile(description="Professional event coverage across Kigali and beyond.")
    other_vendor = create_vendor_profile(description="Professional event coverage across Kigali and beyond.")
    matching = create_inquiry(
        vendor=vendor,
        client_name="Aline Planner",
        client_email="aline@example.com",
        message="We need decor for a lakeside reception.",
        is_read=False,
        event_date=date(2026, 8, 10),
        created_at=datetime(2026, 8, 10, tzinfo=timezone.utc),
    )
    create_inquiry(
        vendor=vendor,
        client_name="Read Planner",
        client_email="read@example.com",
        message="We need decor too.",
        is_read=True,
        event_date=date(2026, 8, 12),
        created_at=datetime(2026, 8, 12, tzinfo=timezone.utc),
    )
    create_inquiry(
        vendor=vendor,
        client_name="Outside Range",
        client_email="outside@example.com",
        message="We need decor.",
        is_read=False,
        event_date=date(2026, 9, 1),
        created_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
    )
    create_inquiry(
        vendor=other_vendor,
        client_name="Other Vendor",
        client_email="other@example.com",
        message="We need decor.",
        is_read=False,
        event_date=date(2026, 8, 10),
        created_at=datetime(2026, 8, 10, tzinfo=timezone.utc),
    )

    page = DjangoInquiryRepository().search(
        vendor.id,
        "decor",
        "unread",
        (date(2026, 8, 1), date(2026, 8, 31)),
        PageRequest(limit=10),
    )

    assert page.total == 1
    assert [item.id for item in page.items] == [matching.id]


def test_inquiry_repository_search_answered_returns_empty_until_answer_signal_exists():
    vendor = create_vendor_profile(description="Professional event coverage across Kigali and beyond.")
    create_inquiry(vendor=vendor, is_read=True)

    page = DjangoInquiryRepository().search(vendor.id, None, "answered", None)

    assert page.total == 0
    assert page.items == []
