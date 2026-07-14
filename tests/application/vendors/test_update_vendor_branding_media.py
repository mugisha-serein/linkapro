from __future__ import annotations

import uuid

import pytest

from application.vendors.commands import AuthenticatedActor
from application.vendors.errors import VendorOperationForbidden, VendorVersionConflict
from application.vendors.handlers import VendorCommandHandlers
from application.vendors.vendor_branding_commands import UpdateVendorBrandingMediaCommand
from domain.vendors.profile.entity import ServiceCategory, VendorProfile
from domain.vendors.profile.errors import VendorProfileValidationError


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


class DenyOwner:
    def __init__(self):
        self.calls = []

    def assert_actor_owns_vendor(self, actor, vendor_id):
        self.calls.append((actor, vendor_id))
        raise VendorOperationForbidden("Actor does not own this vendor.")


class VendorRepo:
    def __init__(self, profile):
        self.profile = profile
        self.get_by_id_calls = []

    def get_by_id(self, vendor_id):
        self.get_by_id_calls.append(vendor_id)
        return self.profile if self.profile.id == vendor_id else None


class AggregateMutationUow:
    def __init__(self):
        self.save_calls = []
        self.events = []

    def save_with_pending_events(self, aggregate, *, expected_version):
        self.save_calls.append((aggregate, expected_version))
        self.events.extend(aggregate.pull_events())
        return aggregate


class UnusedReorderUow:
    def load_active_vendor_images(self, vendor_id):
        raise AssertionError("Portfolio reorder must not be used.")

    def persist_reorder(self, vendor_id, images, *, expected_versions):
        raise AssertionError("Portfolio reorder must not be used.")


def _profile(*, version: int = 4) -> VendorProfile:
    return VendorProfile(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        business_name="Serein Photography",
        category=ServiceCategory.PHOTOGRAPHY,
        description="Professional event photography services across Rwanda.",
        service_area="Kigali",
        contact_email="vendor@example.com",
        contact_phone="+250788123456",
        version=version,
    )


def _handler(vendor_repo, aggregate_uow, authorization):
    unused = StrictUnusedDependency()
    return VendorCommandHandlers(
        vendor_repo=vendor_repo,
        image_repo=unused,
        package_repo=unused,
        inquiry_repo=unused,
        reorder_uow=UnusedReorderUow(),
        aggregate_uow=aggregate_uow,
        authorization_port=authorization,
        idempotency_port=unused,
        inquiry_abuse_protection_port=unused,
        portfolio_creation_port=unused,
    )


def test_update_vendor_branding_media_command_coerces_vendor_id():
    actor = AuthenticatedActor(user_id=uuid.uuid4())
    vendor_id = uuid.uuid4()

    command = UpdateVendorBrandingMediaCommand(
        actor=actor,
        vendor_id=str(vendor_id),
        expected_version=3,
        profile_image_url="https://res.cloudinary.com/demo/image/upload/profile.jpg",
        profile_image_public_id="vendors/profile",
        cover_image_url="https://res.cloudinary.com/demo/image/upload/cover.jpg",
        cover_image_public_id="vendors/cover",
    )

    assert command.actor is actor
    assert command.vendor_id == vendor_id
    assert command.expected_version == 3


def test_update_vendor_branding_media_persists_state_and_event():
    profile = _profile(version=4)
    actor = AuthenticatedActor(user_id=profile.user_id)
    vendor_repo = VendorRepo(profile)
    aggregate_uow = AggregateMutationUow()
    authorization = AllowOwner()
    handler = _handler(vendor_repo, aggregate_uow, authorization)

    result = handler.update_vendor_branding_media(
        UpdateVendorBrandingMediaCommand(
            actor=actor,
            vendor_id=profile.id,
            expected_version=4,
            profile_image_url="https://res.cloudinary.com/demo/image/upload/profile.jpg",
            profile_image_public_id="vendors/profile",
            cover_image_url="https://res.cloudinary.com/demo/image/upload/cover.jpg",
            cover_image_public_id="vendors/cover",
        )
    )

    assert authorization.calls == [(actor, profile.id)]
    assert vendor_repo.get_by_id_calls == [profile.id]
    assert len(aggregate_uow.save_calls) == 1
    saved, expected_version = aggregate_uow.save_calls[0]
    assert saved is profile
    assert expected_version == 4
    assert [event.__class__.__name__ for event in aggregate_uow.events] == ["VendorProfileUpdated"]
    assert result.profile_image_url == "https://res.cloudinary.com/demo/image/upload/profile.jpg"
    assert result.cover_image_url == "https://res.cloudinary.com/demo/image/upload/cover.jpg"
    assert profile.profile_image_public_id == "vendors/profile"
    assert profile.cover_image_public_id == "vendors/cover"
    assert result.version == 5


def test_update_vendor_branding_media_stale_version_prevents_transition_and_persistence():
    profile = _profile(version=4)
    aggregate_uow = AggregateMutationUow()
    handler = _handler(VendorRepo(profile), aggregate_uow, AllowOwner())

    with pytest.raises(VendorVersionConflict) as exc_info:
        handler.update_vendor_branding_media(
            UpdateVendorBrandingMediaCommand(
                actor=AuthenticatedActor(user_id=profile.user_id),
                vendor_id=profile.id,
                expected_version=2,
                profile_image_url="https://res.cloudinary.com/demo/image/upload/profile.jpg",
                profile_image_public_id="vendors/profile",
                cover_image_url=None,
                cover_image_public_id=None,
            )
        )

    conflict = exc_info.value
    assert conflict.resource_id == profile.id
    assert conflict.expected_version == 2
    assert conflict.actual_version == 4
    assert aggregate_uow.save_calls == []
    assert profile.profile_image_url is None
    assert profile.profile_image_public_id is None
    assert profile.version == 4


def test_update_vendor_branding_media_requires_vendor_ownership_before_loading():
    profile = _profile(version=4)
    vendor_repo = VendorRepo(profile)
    aggregate_uow = AggregateMutationUow()
    authorization = DenyOwner()
    handler = _handler(vendor_repo, aggregate_uow, authorization)
    actor = AuthenticatedActor(user_id=uuid.uuid4())

    with pytest.raises(VendorOperationForbidden):
        handler.update_vendor_branding_media(
            UpdateVendorBrandingMediaCommand(
                actor=actor,
                vendor_id=profile.id,
                expected_version=4,
                profile_image_url=None,
                profile_image_public_id=None,
                cover_image_url=None,
                cover_image_public_id=None,
            )
        )

    assert authorization.calls == [(actor, profile.id)]
    assert vendor_repo.get_by_id_calls == []
    assert aggregate_uow.save_calls == []


def test_update_vendor_branding_media_invalid_asset_pair_does_not_persist():
    profile = _profile(version=4)
    aggregate_uow = AggregateMutationUow()
    handler = _handler(VendorRepo(profile), aggregate_uow, AllowOwner())

    with pytest.raises(VendorProfileValidationError) as exc_info:
        handler.update_vendor_branding_media(
            UpdateVendorBrandingMediaCommand(
                actor=AuthenticatedActor(user_id=profile.user_id),
                vendor_id=profile.id,
                expected_version=4,
                profile_image_url="https://res.cloudinary.com/demo/image/upload/profile.jpg",
                profile_image_public_id=None,
                cover_image_url=None,
                cover_image_public_id=None,
            )
        )

    assert "profile_image_public_id" in exc_info.value.field_errors
    assert aggregate_uow.save_calls == []
    assert profile.profile_image_url is None
    assert profile.profile_image_public_id is None
    assert profile.version == 4
