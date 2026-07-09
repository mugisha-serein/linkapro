from __future__ import annotations

import uuid

import pytest

from application.vendors.commands import AuthenticatedActor, UpdateVendorProfileCommand
from application.vendors.handlers import VendorCommandHandlers
from domain.vendors.entities import VendorProfile
from domain.vendors.events import VendorProfileUpdated


class EventPersistenceFailed(RuntimeError):
    pass


class VendorRepository:
    def __init__(self, profile: VendorProfile):
        self.profile = profile

    def get_by_id(self, vendor_id: uuid.UUID):
        return self.profile if vendor_id == self.profile.id else None


class AuthorizationPort:
    def assert_actor_owns_vendor(self, actor, vendor_id):
        return None


class StrictMutationUnitOfWork:
    """Models aggregate and event persistence as one all-or-nothing commit."""

    def __init__(self, profile: VendorProfile):
        self.committed_versions = {profile.id: profile.version}
        self.committed_events = []
        self.staged_versions = {}
        self.aggregate_persistence_succeeded = False
        self.event_persistence_attempted = False
        self.rolled_back = False

    def save_with_pending_events(self, aggregate, *, expected_version):
        assert expected_version == self.committed_versions[aggregate.id]
        pending_events = tuple(aggregate._events)
        assert pending_events, "A mutation must carry its pending domain event into the unit of work."

        self.staged_versions[aggregate.id] = aggregate.version
        self.aggregate_persistence_succeeded = True
        self.event_persistence_attempted = True

        try:
            raise EventPersistenceFailed("event persistence failed")
        except EventPersistenceFailed:
            self.staged_versions.clear()
            self.rolled_back = True
            raise


def test_vendor_mutation_fails_atomically_when_event_persistence_fails_after_aggregate_write():
    actor = AuthenticatedActor(user_id=uuid.uuid4())
    profile = VendorProfile.create_draft(
        user_id=actor.user_id,
        business_name="Original Vendor",
        category="catering",
        description="Reliable vendor services for complete event support.",
        service_area="Kigali",
        contact_email="vendor@example.com",
        contact_phone="+250700000000",
    )
    repository = VendorRepository(profile)
    unit_of_work = StrictMutationUnitOfWork(profile)
    handler = VendorCommandHandlers(
        vendor_repo=repository,
        image_repo=object(),
        package_repo=object(),
        inquiry_repo=object(),
        event_dispatcher=object(),
        reorder_uow=object(),
        aggregate_uow=unit_of_work,
        authorization_port=AuthorizationPort(),
    )

    with pytest.raises(EventPersistenceFailed, match="event persistence failed"):
        handler.update_profile(
            UpdateVendorProfileCommand(
                actor=actor,
                vendor_id=profile.id,
                expected_version=0,
                business_name="Updated Vendor",
            )
        )

    assert unit_of_work.aggregate_persistence_succeeded is True
    assert unit_of_work.event_persistence_attempted is True
    assert unit_of_work.rolled_back is True
    assert unit_of_work.staged_versions == {}
    assert unit_of_work.committed_versions == {profile.id: 0}
    assert unit_of_work.committed_events == []

    pending_events = profile.pull_events()
    assert len(pending_events) == 1
    assert isinstance(pending_events[0], VendorProfileUpdated)
    assert pending_events[0].aggregate_version == 1
