from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import inspect
from threading import Barrier, Lock
import uuid
from typing import get_type_hints

import pytest

import application.vendors.shared.ports as vendor_ports
from application.vendors.portfolio.commands import AddPortfolioImageCommand
from application.vendors.shared.commands import AuthenticatedActor
from application.vendors.errors import VendorApplicationConfigurationError
from application.vendors.shared.handlers import VendorCommandHandlers
from application.vendors.portfolio.ports import PortfolioImageCreationPort
from domain.shared.utils import utc_now
from domain.vendors.portfolio.entity import PortfolioImage
from domain.vendors.profile.entity import ServiceCategory, VendorProfile, VendorStatus


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


class VendorRepo:
    def __init__(self, profile: VendorProfile):
        self.profile = profile
        self.get_by_id_calls: list[uuid.UUID] = []

    def get_by_id(self, vendor_id: uuid.UUID) -> VendorProfile | None:
        self.get_by_id_calls.append(vendor_id)
        return self.profile if self.profile.id == vendor_id else None


class AllowOwner:
    def assert_actor_owns_vendor(self, actor: AuthenticatedActor, vendor_id: uuid.UUID) -> None:
        return None


class PassThroughIdempotency:
    def execute_once(self, *, scope, actor_id, key, payload_fingerprint, operation):
        return operation()


class StrictAtomicPortfolioCreationFake:
    """Serializes competing calls and owns both next-order selection and persistence."""

    def __init__(self, concurrent_call_count: int = 2):
        self._start = Barrier(concurrent_call_count)
        self._lock = Lock()
        self.images: list[PortfolioImage] = []
        self.calls: list[uuid.UUID] = []

    def create_at_next_order(self, *, vendor_id: uuid.UUID, image_factory):
        self._start.wait(timeout=5)
        with self._lock:
            next_order = max(
                (image.order for image in self.images if image.vendor_id == vendor_id),
                default=-1,
            ) + 1
            image = image_factory(next_order)
            assert image.vendor_id == vendor_id
            assert image.order == next_order
            assert all(
                existing.vendor_id != vendor_id or existing.order != next_order
                for existing in self.images
            )
            self.calls.append(vendor_id)
            self.images.append(image)
            return image


def _approved_profile(vendor_id: uuid.UUID) -> VendorProfile:
    now = utc_now()
    return VendorProfile(
        id=vendor_id,
        user_id=uuid.uuid4(),
        business_name="Vendor",
        category=ServiceCategory.CATERING,
        description="Reliable vendor services for complete event support.",
        service_area="Kigali",
        contact_email="vendor@example.com",
        contact_phone="+250700000000",
        status=VendorStatus.APPROVED,
        created_at=now,
        updated_at=now,
        submitted_at=now,
        approved_at=now,
    )


def _handler(*, profile: VendorProfile, creation_port) -> VendorCommandHandlers:
    unused = StrictUnusedDependency()
    return VendorCommandHandlers(
        vendor_repo=VendorRepo(profile),
        image_repo=unused,
        package_repo=unused,
        inquiry_repo=unused,
        reorder_uow=unused,
        aggregate_uow=unused,
        authorization_port=AllowOwner(),
        idempotency_port=PassThroughIdempotency(),
        inquiry_abuse_protection_port=unused,
        portfolio_creation_port=creation_port,
    )


def test_portfolio_image_creation_port_replaces_order_allocator_contract():
    signature = inspect.signature(PortfolioImageCreationPort.create_at_next_order)
    hints = get_type_hints(PortfolioImageCreationPort.create_at_next_order)

    assert not hasattr(vendor_ports, "PortfolioOrderAllocator")
    assert tuple(signature.parameters) == ("self", "vendor_id", "image_factory")
    assert signature.parameters["vendor_id"].kind is inspect.Parameter.KEYWORD_ONLY
    assert signature.parameters["image_factory"].kind is inspect.Parameter.KEYWORD_ONLY
    assert hints["vendor_id"] is uuid.UUID
    assert hints["return"] is PortfolioImage

    handler_signature = inspect.signature(VendorCommandHandlers.__init__)
    assert handler_signature.parameters["portfolio_creation_port"].default is inspect.Parameter.empty


def test_handler_composition_requires_atomic_portfolio_creation_port():
    vendor_id = uuid.uuid4()
    profile = _approved_profile(vendor_id)
    unused = StrictUnusedDependency()

    with pytest.raises(VendorApplicationConfigurationError) as exc_info:
        VendorCommandHandlers(
            vendor_repo=VendorRepo(profile),
            image_repo=unused,
            package_repo=unused,
            inquiry_repo=unused,
            reorder_uow=unused,
            aggregate_uow=unused,
            authorization_port=AllowOwner(),
            idempotency_port=PassThroughIdempotency(),
            inquiry_abuse_protection_port=unused,
            portfolio_creation_port=None,
        )

    assert exc_info.value.field_errors == {
        "portfolio_creation_port": ["Required dependency is missing."]
    }


def test_concurrent_add_portfolio_image_calls_receive_unique_contiguous_orders_from_strict_fake():
    vendor_id = uuid.uuid4()
    profile = _approved_profile(vendor_id)
    creation_port = StrictAtomicPortfolioCreationFake()
    handler = _handler(profile=profile, creation_port=creation_port)

    commands = (
        AddPortfolioImageCommand(
            actor=AuthenticatedActor(user_id=profile.user_id),
            vendor_id=vendor_id,
            public_id="asset-one",
            secure_url="https://example.com/one.jpg",
            caption="One",
            idempotency_key="portfolio-image-one",
        ),
        AddPortfolioImageCommand(
            actor=AuthenticatedActor(user_id=profile.user_id),
            vendor_id=vendor_id,
            public_id="asset-two",
            secure_url="https://example.com/two.jpg",
            caption="Two",
            idempotency_key="portfolio-image-two",
        ),
    )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = tuple(executor.map(handler.add_portfolio_image, commands))

    assert sorted(result.order for result in results) == [0, 1]
    assert {result.secure_url for result in results} == {
        "https://example.com/one.jpg",
        "https://example.com/two.jpg",
    }
    assert {result.caption for result in results} == {"One", "Two"}
    assert creation_port.calls == [vendor_id, vendor_id]
    assert sorted(image.order for image in creation_port.images) == [0, 1]
    assert len({image.id for image in creation_port.images}) == 2
