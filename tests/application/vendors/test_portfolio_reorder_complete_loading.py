from __future__ import annotations

import inspect
from typing import Sequence, get_type_hints
import uuid

from application.vendors.commands import (
    AuthenticatedActor,
    ReorderPortfolioImagesCommand,
    ResourceVersion,
)
from application.vendors.handlers import VendorCommandHandlers
from application.vendors.ports import PortfolioReorderUnitOfWork
from domain.vendors.portfolio.entity import PortfolioImage


class StrictUnusedDependency:
    def __getattr__(self, name):
        raise AssertionError(f"Unexpected dependency access: {name}")

    def get_by_id(self, *args, **kwargs): self.__getattr__("get_by_id")
    def get_by_user_id(self, *args, **kwargs): self.__getattr__("get_by_user_id")
    def get_for_vendor(self, *args, **kwargs): self.__getattr__("get_for_vendor")
    def add_with_pending_events(self, *args, **kwargs): self.__getattr__("add_with_pending_events")
    def save_with_pending_events(self, *args, **kwargs): self.__getattr__("save_with_pending_events")
    def assert_actor_owns_vendor(self, *args, **kwargs): self.__getattr__("assert_actor_owns_vendor")
    def assert_actor_can_access_vendor(self, *args, **kwargs): self.__getattr__("assert_actor_can_access_vendor")
    def assert_moderator_can_moderate_vendor(self, *args, **kwargs): self.__getattr__("assert_moderator_can_moderate_vendor")
    def execute_once(self, *args, **kwargs): self.__getattr__("execute_once")
    def assert_inquiry_allowed(self, *args, **kwargs): self.__getattr__("assert_inquiry_allowed")
    def load_active_vendor_images(self, *args, **kwargs): self.__getattr__("load_active_vendor_images")
    def persist_reorder(self, *args, **kwargs): self.__getattr__("persist_reorder")
    def create_at_next_order(self, *args, **kwargs): self.__getattr__("create_at_next_order")


class AllowOwner:
    def __init__(self):
        self.calls = []

    def assert_actor_owns_vendor(self, actor, vendor_id):
        self.calls.append((actor, vendor_id))


class CompleteActivePortfolioReorderUow:
    def __init__(self, images):
        self.images = tuple(images)
        self.load_calls = []
        self.persist_calls = []

    def load_active_vendor_images(self, vendor_id):
        self.load_calls.append(vendor_id)
        assert all(image.vendor_id == vendor_id for image in self.images)
        assert all(image.is_active and not image.is_deleted for image in self.images)
        return self.images

    def persist_reorder(self, vendor_id, images, *, expected_versions):
        persisted = tuple(images)
        self.persist_calls.append((vendor_id, persisted, expected_versions))
        return persisted


def _image(vendor_id: uuid.UUID, order: int) -> PortfolioImage:
    return PortfolioImage(
        id=uuid.uuid4(),
        vendor_id=vendor_id,
        public_id=f"asset-{order}",
        secure_url=f"https://example.com/portfolio/{order}.jpg",
        caption=f"Image {order}",
        order=order,
        version=0,
    )


def _handler(reorder_uow, authorization_port):
    unused = StrictUnusedDependency()
    return VendorCommandHandlers(
        vendor_repo=unused,
        image_repo=unused,
        package_repo=unused,
        inquiry_repo=unused,
        reorder_uow=reorder_uow,
        authorization_port=authorization_port,
        aggregate_uow=unused,
        idempotency_port=unused,
        inquiry_abuse_protection_port=unused,
        portfolio_creation_port=unused,
    )


def test_reorder_uow_contract_loads_complete_active_set_without_pagination():
    signature = inspect.signature(PortfolioReorderUnitOfWork.load_active_vendor_images)
    type_hints = get_type_hints(PortfolioReorderUnitOfWork.load_active_vendor_images)

    assert tuple(signature.parameters) == ("self", "vendor_id")
    assert type_hints["return"] == Sequence[PortfolioImage]
    assert not hasattr(PortfolioReorderUnitOfWork, "list_vendor_images")


def test_reorder_loads_and_returns_complete_portfolio_with_more_than_100_items():
    vendor_id = uuid.uuid4()
    actor = AuthenticatedActor(user_id=uuid.uuid4())
    images = tuple(_image(vendor_id, order) for order in range(125))
    requested = images[1:] + images[:1]
    reorder_uow = CompleteActivePortfolioReorderUow(images)
    authorization = AllowOwner()
    handler = _handler(reorder_uow, authorization)

    result = handler.reorder_portfolio_images(
        ReorderPortfolioImagesCommand(
            actor=actor,
            vendor_id=vendor_id,
            image_ids_in_order=tuple(image.id for image in requested),
            expected_versions=tuple(
                ResourceVersion(resource_id=image.id, expected_version=image.version)
                for image in requested
            ),
        )
    )

    requested_ids = tuple(image.id for image in requested)
    assert reorder_uow.load_calls == [vendor_id]
    assert authorization.calls == [(actor, vendor_id)]
    assert len(result.items) == 125
    assert result.total == 125
    assert result.limit == 125
    assert result.offset == 0
    assert tuple(item.id for item in result.items) == requested_ids

    assert len(reorder_uow.persist_calls) == 1
    persisted_vendor_id, persisted_images, expected_versions = reorder_uow.persist_calls[0]
    assert persisted_vendor_id == vendor_id
    assert tuple(image.id for image in persisted_images) == requested_ids
    assert tuple(expected_versions) == requested_ids
