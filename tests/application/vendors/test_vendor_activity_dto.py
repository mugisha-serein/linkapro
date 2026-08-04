from __future__ import annotations

from dataclasses import FrozenInstanceError, fields
import inspect
from typing import get_args, get_origin, get_type_hints
import uuid

import pytest

from application.vendors.commands import AuthenticatedActor
from application.vendors.dtos import PageDTO, VendorActivityDTO
from application.vendors.handlers import VendorQueryHandlers
from application.vendors.ports import VendorReadPort
from application.vendors.queries import ListRecentVendorActivityQuery
from domain.vendors.interfaces import PageRequest


class StrictUnusedRepository:
    def __getattr__(self, name):
        raise AssertionError(f"Unexpected repository access: {name}")


class AuthorizationPort:
    def __init__(self):
        self.calls = []

    def assert_actor_can_access_vendor(self, actor, vendor_id):
        self.calls.append((actor, vendor_id))


class ActivityReadPort:
    def __init__(self, activity_page):
        self.activity_page = activity_page
        self.calls = []

    def recent_activity(self, vendor_id, page):
        self.calls.append((vendor_id, page))
        return self.activity_page

    def dashboard_summary(self, vendor_id):
        raise AssertionError("Dashboard summary must not be queried.")

    def analytics(self, vendor_id):
        raise AssertionError("Analytics must not be queried.")

    def list_service_packages(self, vendor_id, page):
        raise AssertionError("Service packages must not be queried.")


def _activity() -> VendorActivityDTO:
    return VendorActivityDTO(
        id="8c867cc5-c782-43a8-98f1-bc1092192615",
        type="inquiry_received",
        message="Inquiry from Planner",
        created_at="2026-07-09T09:15:00+00:00",
    )


def _handler(read_port, authorization):
    unused = StrictUnusedRepository()
    return VendorQueryHandlers(
        vendor_repo=unused,
        image_repo=unused,
        inquiry_repo=unused,
        read_repo=read_port,
        authorization_port=authorization,
    )


def test_vendor_activity_dto_is_immutable_and_has_the_existing_item_shape():
    activity = _activity()
    hints = get_type_hints(VendorActivityDTO)

    assert tuple(field.name for field in fields(VendorActivityDTO)) == (
        "id",
        "type",
        "message",
        "created_at",
    )
    assert hints == {
        "id": str,
        "type": str,
        "message": str,
        "created_at": str,
    }

    with pytest.raises(FrozenInstanceError):
        activity.message = "Changed"


def test_vendor_read_port_recent_activity_returns_page_of_activity_dtos():
    signature = inspect.signature(VendorReadPort.recent_activity)
    hints = get_type_hints(VendorReadPort.recent_activity)
    return_type = hints["return"]

    assert tuple(signature.parameters) == ("self", "vendor_id", "page")
    assert hints["vendor_id"] is uuid.UUID
    assert hints["page"] is PageRequest
    assert get_origin(return_type) is PageDTO
    assert get_args(return_type) == (VendorActivityDTO,)


def test_vendor_query_handler_authorizes_and_preserves_activity_page_and_pagination():
    vendor_id = uuid.uuid4()
    actor = AuthenticatedActor(user_id=uuid.uuid4())
    requested_page = PageRequest(limit=4, offset=8)
    activity_page = PageDTO(
        items=(_activity(),),
        total=13,
        limit=4,
        offset=8,
        next_cursor="next-activity-page",
    )
    read_port = ActivityReadPort(activity_page)
    authorization = AuthorizationPort()
    handler = _handler(read_port, authorization)

    result = handler.get_recent_activity(
        ListRecentVendorActivityQuery(
            actor=actor,
            vendor_id=vendor_id,
            page=requested_page,
        )
    )

    assert result is activity_page
    assert result.items == activity_page.items
    assert result.total == 13
    assert result.limit == 4
    assert result.offset == 8
    assert result.next_cursor == "next-activity-page"
    assert authorization.calls == [(actor, vendor_id)]
    assert read_port.calls == [(vendor_id, requested_page)]


def test_vendor_query_handler_recent_activity_keeps_default_pagination():
    vendor_id = uuid.uuid4()
    actor = AuthenticatedActor(user_id=uuid.uuid4())
    activity_page = PageDTO(items=(), total=0, limit=10, offset=0)
    read_port = ActivityReadPort(activity_page)
    handler = _handler(read_port, AuthorizationPort())

    result = handler.get_recent_activity(
        ListRecentVendorActivityQuery(actor=actor, vendor_id=vendor_id)
    )

    assert result is activity_page
    assert len(read_port.calls) == 1
    called_vendor_id, called_page = read_port.calls[0]
    assert called_vendor_id == vendor_id
    assert called_page.limit == 10
    assert called_page.offset == 0


def test_vendor_query_handler_recent_activity_return_annotation_is_typed():
    return_type = get_type_hints(VendorQueryHandlers.get_recent_activity)["return"]

    assert get_origin(return_type) is PageDTO
    assert get_args(return_type) == (VendorActivityDTO,)
