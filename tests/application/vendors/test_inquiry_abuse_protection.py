from __future__ import annotations

from datetime import timedelta
import inspect
import uuid
from typing import get_type_hints

import pytest

from application.vendors.commands import SendInquiryCommand
from application.vendors.errors import InquiryAbuseDenied, VendorApplicationConfigurationError
from application.vendors.handlers import VendorCommandHandlers
from application.vendors.ports import InquiryAbuseProtectionPort
from domain.shared.utils import utc_now
from domain.vendors.entities import ServiceCategory, VendorProfile, VendorStatus


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
    def __init__(self, profile, trace):
        self.profile = profile
        self.trace = trace
        self.get_by_id_calls = []

    def get_by_id(self, vendor_id):
        self.trace.append("vendor-load")
        self.get_by_id_calls.append(vendor_id)
        return self.profile if self.profile.id == vendor_id else None


class AggregateUow:
    def __init__(self, trace):
        self.trace = trace
        self.add_calls = []
        self.events = []

    def add_with_pending_events(self, aggregate):
        self.trace.append("inquiry-add")
        self.add_calls.append(aggregate)
        self.events.extend(aggregate.pull_events())
        return aggregate

    def save_with_pending_events(self, aggregate, *, expected_version):
        raise AssertionError("Inquiry creation must not use the update mutation path.")


class IdempotencyPort:
    def __init__(self):
        self.records = {}

    def execute_once(self, *, scope, actor_id, key, payload_fingerprint, operation):
        record_key = (scope, actor_id, key)
        if record_key in self.records:
            return self.records[record_key]
        result = operation()
        self.records[record_key] = result
        return result


class AllowInquiryAbuseProtection:
    def __init__(self, trace):
        self.trace = trace
        self.calls = []

    def assert_inquiry_allowed(self, *, requester_identity, vendor_id, payload_digest):
        self.trace.append("abuse-check")
        self.calls.append((requester_identity, vendor_id, payload_digest))


class DenyInquiryAbuseProtection:
    def __init__(self, trace):
        self.trace = trace
        self.calls = []

    def assert_inquiry_allowed(self, *, requester_identity, vendor_id, payload_digest):
        self.trace.append("abuse-check")
        self.calls.append((requester_identity, vendor_id, payload_digest))
        raise InquiryAbuseDenied()


class UnusedReorderUow:
    def load_active_vendor_images(self, vendor_id):
        raise AssertionError("Portfolio reorder must not be used.")

    def persist_reorder(self, vendor_id, images, *, expected_versions):
        raise AssertionError("Portfolio reorder must not be used.")


def _approved_profile(vendor_id: uuid.UUID) -> VendorProfile:
    now = utc_now()
    return VendorProfile(
        id=vendor_id,
        user_id=uuid.uuid4(),
        business_name="Approved Vendor",
        category=ServiceCategory.CATERING,
        description="Reliable catering services for private and corporate events.",
        service_area="Kigali",
        contact_email="vendor@example.com",
        contact_phone="+250788123456",
        status=VendorStatus.APPROVED,
        created_at=now - timedelta(days=2),
        updated_at=now,
        submitted_at=now - timedelta(days=1),
        approved_at=now,
    )


def _command(vendor_id: uuid.UUID, requester_id: uuid.UUID, *, key: str = "send-inquiry") -> SendInquiryCommand:
    return SendInquiryCommand(
        vendor_id=vendor_id,
        requester_id=requester_id,
        client_name="Planner",
        client_email="planner@example.com",
        client_phone="+250788654321",
        message="Can you support our event next month?",
        idempotency_key=key,
    )


def _handler(*, vendor_repo, aggregate_uow, idempotency_port, abuse_port):
    unused = StrictUnusedDependency()
    return VendorCommandHandlers(
        vendor_repo=vendor_repo,
        image_repo=unused,
        package_repo=unused,
        inquiry_repo=unused,
        reorder_uow=UnusedReorderUow(),
        aggregate_uow=aggregate_uow,
        idempotency_port=idempotency_port,
        inquiry_abuse_protection_port=abuse_port,
        authorization_port=unused,
        portfolio_creation_port=unused,
    )


def test_inquiry_abuse_protection_port_contract_receives_identity_vendor_and_digest():
    signature = inspect.signature(InquiryAbuseProtectionPort.assert_inquiry_allowed)
    hints = get_type_hints(InquiryAbuseProtectionPort.assert_inquiry_allowed)

    assert tuple(signature.parameters) == (
        "self",
        "requester_identity",
        "vendor_id",
        "payload_digest",
    )
    assert hints["requester_identity"] is uuid.UUID
    assert hints["vendor_id"] is uuid.UUID
    assert hints["payload_digest"] is str
    assert hints["return"] is type(None)


def test_send_inquiry_calls_abuse_protection_before_loading_vendor_and_creating_inquiry():
    trace = []
    vendor_id = uuid.uuid4()
    requester_id = uuid.uuid4()
    profile = _approved_profile(vendor_id)
    vendor_repo = VendorRepo(profile, trace)
    aggregate_uow = AggregateUow(trace)
    abuse_port = AllowInquiryAbuseProtection(trace)
    handler = _handler(
        vendor_repo=vendor_repo,
        aggregate_uow=aggregate_uow,
        idempotency_port=IdempotencyPort(),
        abuse_port=abuse_port,
    )

    result = handler.send_inquiry(_command(vendor_id, requester_id))

    assert trace == ["abuse-check", "vendor-load", "inquiry-add"]
    assert vendor_repo.get_by_id_calls == [vendor_id]
    assert len(aggregate_uow.add_calls) == 1
    assert result.vendor_id == vendor_id
    assert len(abuse_port.calls) == 1
    received_requester, received_vendor, payload_digest = abuse_port.calls[0]
    assert received_requester == requester_id
    assert received_vendor == vendor_id
    assert len(payload_digest) == 64
    assert set(payload_digest) <= set("0123456789abcdef")


def test_inquiry_payload_digest_is_stable_and_excludes_idempotency_key():
    vendor_id = uuid.uuid4()
    requester_id = uuid.uuid4()
    first = _command(vendor_id, requester_id, key="first-key")
    replay = _command(vendor_id, requester_id, key="second-key")
    changed = SendInquiryCommand(
        vendor_id=vendor_id,
        requester_id=requester_id,
        client_name="Planner",
        client_email="planner@example.com",
        client_phone="+250788654321",
        message="A different inquiry payload.",
        idempotency_key="first-key",
    )

    assert VendorCommandHandlers._inquiry_payload_digest(first) == VendorCommandHandlers._inquiry_payload_digest(replay)
    assert VendorCommandHandlers._inquiry_payload_digest(first) != VendorCommandHandlers._inquiry_payload_digest(changed)


def test_typed_abuse_denial_stops_before_vendor_load_and_inquiry_creation():
    trace = []
    vendor_id = uuid.uuid4()
    requester_id = uuid.uuid4()
    vendor_repo = VendorRepo(_approved_profile(vendor_id), trace)
    aggregate_uow = AggregateUow(trace)
    idempotency_port = IdempotencyPort()
    abuse_port = DenyInquiryAbuseProtection(trace)
    handler = _handler(
        vendor_repo=vendor_repo,
        aggregate_uow=aggregate_uow,
        idempotency_port=idempotency_port,
        abuse_port=abuse_port,
    )

    with pytest.raises(InquiryAbuseDenied) as exc_info:
        handler.send_inquiry(_command(vendor_id, requester_id))

    assert exc_info.value.code == "inquiry_abuse_denied"
    assert trace == ["abuse-check"]
    assert vendor_repo.get_by_id_calls == []
    assert aggregate_uow.add_calls == []
    assert aggregate_uow.events == []
    assert idempotency_port.records == {}


def test_send_inquiry_requires_abuse_protection_port_before_vendor_load():
    trace = []
    vendor_id = uuid.uuid4()
    vendor_repo = VendorRepo(_approved_profile(vendor_id), trace)
    aggregate_uow = AggregateUow(trace)
    handler = _handler(
        vendor_repo=vendor_repo,
        aggregate_uow=aggregate_uow,
        idempotency_port=IdempotencyPort(),
        abuse_port=None,
    )

    with pytest.raises(VendorApplicationConfigurationError) as exc_info:
        handler.send_inquiry(_command(vendor_id, uuid.uuid4()))

    assert exc_info.value.field_errors == {
        "inquiry_abuse_protection_port": ["Inquiry abuse protection is required."]
    }
    assert trace == []
    assert vendor_repo.get_by_id_calls == []
    assert aggregate_uow.add_calls == []
