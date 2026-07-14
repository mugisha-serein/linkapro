from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch
import uuid

from application.vendors.inquiries.dtos import InquiryDTO
from application.vendors.inquiries.queries import ListInquiriesQuery
from application.vendors.shared.dtos import PageDTO
from django_app.vendors.views.inquiries import InquiryListView


def test_inquiry_list_view_passes_q_as_search_text():
    user_id = uuid.uuid4()
    vendor_id = uuid.uuid4()
    request = SimpleNamespace(user=SimpleNamespace(id=user_id), query_params={"q": "  bride  "})
    profile = SimpleNamespace(id=vendor_id)
    handlers = Mock()
    handlers.list_inquiries.return_value = PageDTO(
        items=(
            InquiryDTO(
                id=uuid.uuid4(),
                vendor_id=vendor_id,
                client_name="Bride Planner",
                client_email="bride@example.com",
                client_phone=None,
                message="Can you support our reception?",
                event_date=None,
                is_read=False,
                created_at=datetime(2026, 7, 14, tzinfo=timezone.utc),
                version=0,
            ),
        ),
        total=1,
        limit=50,
        offset=0,
    )

    with patch(
        "django_app.vendors.views.inquiries._get_current_vendor_profile",
        return_value=(profile, None),
    ), patch(
        "django_app.vendors.views.inquiries.get_query_handlers",
        return_value=handlers,
    ):
        response = InquiryListView().get(request)

    query = handlers.list_inquiries.call_args.args[0]
    assert isinstance(query, ListInquiriesQuery)
    assert query.vendor_id == vendor_id
    assert query.actor.user_id == user_id
    assert query.search_text == "bride"
    assert response.status_code == 200
    assert response.data[0]["client_name"] == "Bride Planner"
