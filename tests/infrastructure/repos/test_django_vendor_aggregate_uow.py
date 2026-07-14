from __future__ import annotations

import uuid

import pytest

from application.vendors.errors import VendorApplicationConfigurationError
from domain.vendors.profile.entity import ServiceCategory, VendorProfile
from django_app.identity.models import User
from django_app.vendors.models import VendorDomainEventOutbox
from django_app.vendors.models import VendorProfile as DjangoVendorProfile
from infrastructure.adapters.django_vendor_event_outbox import DjangoVendorEventOutboxDispatcher
from infrastructure.repos.profile.django_aggregate_uow import DjangoVendorAggregateUnitOfWork


pytestmark = pytest.mark.django_db(transaction=True)


def _profile_with_events(user_id: uuid.UUID, count: int = 1) -> VendorProfile:
    profile = VendorProfile.create_draft(
        user_id=user_id,
        business_name="Reliable Events",
        category=ServiceCategory.CATERING,
        description="Reliable catering services for weddings and corporate events.",
        service_area="Kigali",
        contact_email="vendor@example.com",
        contact_phone="+250700000000",
    )
    for index in range(count):
        profile.update_details(business_name=f"Reliable Events {index + 1}")
    return profile


def test_add_persists_aggregate_and_pending_events_atomically():
    user = User.objects.create_user(email="vendor-uow@example.com", password="Password1!", role="vendor")
    profile = _profile_with_events(user.id)
    expected_event = profile._events[0]

    saved = DjangoVendorAggregateUnitOfWork().add_with_pending_events(profile)

    assert saved.id == profile.id
    assert DjangoVendorProfile.objects.filter(id=profile.id).exists()
    outbox = VendorDomainEventOutbox.objects.get(event_id=expected_event.event_id)
    assert outbox.aggregate_id == profile.id
    assert outbox.aggregate_version == expected_event.aggregate_version
    assert profile.pull_events() == []


def test_outbox_failure_rolls_back_aggregate_and_keeps_pending_events():
    class FailingOutbox:
        def dispatch(self, event) -> None:
            raise RuntimeError("outbox unavailable")

    user = User.objects.create_user(email="vendor-uow-fail@example.com", password="Password1!", role="vendor")
    profile = _profile_with_events(user.id)
    expected_event_id = profile._events[0].event_id
    uow = DjangoVendorAggregateUnitOfWork(event_outbox=FailingOutbox())

    with pytest.raises(RuntimeError, match="outbox unavailable"):
        uow.add_with_pending_events(profile)

    assert not DjangoVendorProfile.objects.filter(id=profile.id).exists()
    assert [event.event_id for event in profile._events] == [expected_event_id]
    assert not VendorDomainEventOutbox.objects.filter(event_id=expected_event_id).exists()


def test_aggregate_persistence_failure_creates_no_outbox_rows():
    class FailingRepository:
        def add(self, aggregate):
            raise RuntimeError("aggregate persistence failed")

    user = User.objects.create_user(email="vendor-uow-persist@example.com", password="Password1!", role="vendor")
    profile = _profile_with_events(user.id)
    event_id = profile._events[0].event_id
    uow = DjangoVendorAggregateUnitOfWork(vendor_repo=FailingRepository())

    with pytest.raises(RuntimeError, match="aggregate persistence failed"):
        uow.add_with_pending_events(profile)

    assert not VendorDomainEventOutbox.objects.filter(event_id=event_id).exists()
    assert [event.event_id for event in profile._events] == [event_id]


def test_pending_events_are_persisted_in_aggregate_order():
    class IdentityRepository:
        def add(self, aggregate):
            return aggregate

    class RecordingOutbox:
        def __init__(self) -> None:
            self.event_ids: list[uuid.UUID] = []

        def dispatch(self, event) -> None:
            self.event_ids.append(event.event_id)

    user = User.objects.create_user(email="vendor-uow-order@example.com", password="Password1!", role="vendor")
    profile = _profile_with_events(user.id, count=3)
    expected = [event.event_id for event in profile._events]
    outbox = RecordingOutbox()
    uow = DjangoVendorAggregateUnitOfWork(vendor_repo=IdentityRepository(), event_outbox=outbox)

    saved = uow.add_with_pending_events(profile)

    assert saved is profile
    assert outbox.event_ids == expected
    assert profile.pull_events() == []


def test_event_id_retry_is_idempotent(monkeypatch):
    user = User.objects.create_user(email="vendor-uow-retry@example.com", password="Password1!", role="vendor")
    profile = _profile_with_events(user.id)
    event = profile._events[0]
    dispatcher = DjangoVendorEventOutboxDispatcher()
    scheduled: list[uuid.UUID] = []
    monkeypatch.setattr(dispatcher, "_schedule", lambda event_id: scheduled.append(event_id))

    dispatcher.dispatch(event)
    dispatcher.dispatch(event)

    assert VendorDomainEventOutbox.objects.filter(event_id=event.event_id).count() == 1
    assert len(scheduled) == 1


def test_unsupported_aggregate_fails_with_configuration_error():
    with pytest.raises(VendorApplicationConfigurationError, match="Unsupported vendor aggregate type"):
        DjangoVendorAggregateUnitOfWork().add_with_pending_events(object())
