from __future__ import annotations

import uuid

import pytest

from application.vendors.commands import AuthenticatedActor, UpdateVendorProfileCommand
from application.vendors.errors import VendorOperationForbidden
from application.vendors.handlers import VendorCommandHandlers
from domain.vendors.entities import ServiceCategory, VendorProfile
from tests.application.vendors.strict_vendor_profile_repository import (
    StrictVendorProfileRepository,
)
from tests.application.vendors.test_application_alignment import AuthorizationPort


class VendorProfileRepositoryDelegate:
    def __init__(self, profile: VendorProfile) -> None:
        self.profile = profile
        self.get_by_id_calls: list[uuid.UUID] = []

    def get_by_id(self, vendor_id: uuid.UUID) -> VendorProfile | None:
        self.get_by_id_calls.append(vendor_id)
        return self.profile if vendor_id == self.profile.id else None


class AggregateMutationUnitOfWork:
    def __init__(self) -> None:
        self.save_calls: list[tuple[VendorProfile, int]] = []

    def save_with_pending_events(
        self,
        aggregate: VendorProfile,
        *,
        expected_version: int,
    ) -> VendorProfile:
        self.save_calls.append((aggregate, expected_version))
        aggregate.pull_events()
        return aggregate


class VendorProfileUpdateAuthorizationFake(AuthorizationPort):
    """Application authorization fake configured for actor identity and state."""

    def __init__(
        self,
        *,
        owner_id: uuid.UUID,
        admin_ids: tuple[uuid.UUID, ...] = (),
        suspended_ids: tuple[uuid.UUID, ...] = (),
    ) -> None:
        super().__init__()
        self.owner_id = owner_id
        self.admin_ids = set(admin_ids)
        self.suspended_ids = set(suspended_ids)

    def assert_actor_owns_vendor(self, actor, vendor_id: uuid.UUID) -> None:
        self.calls.append((actor, vendor_id))
        if actor is None:
            raise VendorOperationForbidden("Authentication is required.")
        if actor.user_id in self.suspended_ids:
            raise VendorOperationForbidden("Suspended actors cannot update vendor profiles.")
        if actor.user_id in self.admin_ids:
            raise VendorOperationForbidden("Admin actors do not own vendor profiles.")
        if actor.user_id != self.owner_id:
            raise VendorOperationForbidden("Actor does not own this vendor.")


def _profile(owner_id: uuid.UUID) -> VendorProfile:
    return VendorProfile(
        id=uuid.uuid4(),
        user_id=owner_id,
        business_name="Original Vendor",
        category=ServiceCategory.CATERING,
        description="Reliable vendor services for complete event support.",
        service_area="Kigali",
        contact_email="vendor@example.com",
        contact_phone="+250700000000",
        version=2,
    )


def _command(
    *,
    actor: AuthenticatedActor | None,
    vendor_id: uuid.UUID,
) -> UpdateVendorProfileCommand:
    validated_actor = actor or AuthenticatedActor(user_id=uuid.uuid4())
    command = UpdateVendorProfileCommand(
        actor=validated_actor,
        vendor_id=vendor_id,
        expected_version=2,
        business_name="Updated Vendor",
    )
    if actor is None:
        object.__setattr__(command, "actor", None)
    return command


@pytest.mark.parametrize(
    ("actor_kind", "is_allowed"),
    [
        pytest.param("owner", True, id="owner"),
        pytest.param("another_vendor", False, id="another-vendor"),
        pytest.param("admin", False, id="admin"),
        pytest.param("anonymous", False, id="anonymous"),
        pytest.param("suspended", False, id="suspended"),
    ],
)
def test_update_vendor_profile_authorization_matrix(actor_kind: str, is_allowed: bool):
    owner_id = uuid.uuid4()
    another_vendor_id = uuid.uuid4()
    admin_id = uuid.uuid4()
    suspended_id = uuid.uuid4()
    profile = _profile(owner_id)

    actors = {
        "owner": AuthenticatedActor(user_id=owner_id),
        "another_vendor": AuthenticatedActor(user_id=another_vendor_id),
        "admin": AuthenticatedActor(user_id=admin_id),
        "anonymous": None,
        "suspended": AuthenticatedActor(user_id=suspended_id),
    }
    actor = actors[actor_kind]
    authorization = VendorProfileUpdateAuthorizationFake(
        owner_id=owner_id,
        admin_ids=(admin_id,),
        suspended_ids=(suspended_id,),
    )
    repository_delegate = VendorProfileRepositoryDelegate(profile)
    repository = StrictVendorProfileRepository(repository_delegate)
    aggregate_uow = AggregateMutationUnitOfWork()
    handler = VendorCommandHandlers(
        vendor_repo=repository,
        image_repo=object(),
        package_repo=object(),
        inquiry_repo=object(),
        reorder_uow=object(),
        aggregate_uow=aggregate_uow,
        authorization_port=authorization,
        portfolio_creation_port=object(),
    )
    command = _command(actor=actor, vendor_id=profile.id)

    if is_allowed:
        result = handler.update_profile(command)

        assert result.business_name == "Updated Vendor"
        assert repository_delegate.get_by_id_calls == [profile.id]
        assert len(aggregate_uow.save_calls) == 1
        saved, expected_version = aggregate_uow.save_calls[0]
        assert saved is profile
        assert expected_version == 2
    else:
        with pytest.raises(VendorOperationForbidden):
            handler.update_profile(command)

        assert repository_delegate.get_by_id_calls == []
        assert aggregate_uow.save_calls == []
        assert profile.business_name == "Original Vendor"
        assert profile.version == 2

    assert authorization.calls == [(actor, profile.id)]
