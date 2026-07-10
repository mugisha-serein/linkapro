from __future__ import annotations

import uuid

import pytest

from application.vendors.commands import AuthenticatedActor
from application.vendors.errors import VendorVersionConflict
from application.vendors.handlers import VendorCommandHandlers
from application.vendors.portfolio_media_commands import UpdatePortfolioCaptionCommand
import application.vendors.portfolio_caption_update_handler  # noqa: F401 - registers handler method
from domain.vendors.entities import PortfolioImage, PortfolioQualityStatus, PortfolioUploadStatus, PortfolioVisibilityStatus


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


class ImageRepo:
    def __init__(self, media):
        self.media = media
        self.get_for_vendor_calls = []

    def get_for_vendor(self, vendor_id, media_id):
        self.get_for_vendor_calls.append((vendor_id, media_id))
        if self.media.vendor_id == vendor_id and self.media.id == media_id:
            return self.media
        return None


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


def _media(
    vendor_id: uuid.UUID,
    *,
    caption: str | None = "Old caption",
    visibility_status: str = PortfolioVisibilityStatus.PRIVATE.value,
    version: int = 3,
) -> PortfolioImage:
    return PortfolioImage(
        id=uuid.uuid4(),
        vendor_id=vendor_id,
        public_id="asset",
        secure_url="https://example.com/media.jpg",
        caption=caption,
        upload_status=PortfolioUploadStatus.UPLOADED.value,
        quality_status=PortfolioQualityStatus.PASSED.value,
        visibility_status=visibility_status,
        version=version,
    )


def _handler(image_repo, aggregate_uow, authorization):
    unused = StrictUnusedDependency()
    return VendorCommandHandlers(
        vendor_repo=unused,
        image_repo=image_repo,
        package_repo=unused,
        inquiry_repo=unused,
        reorder_uow=UnusedReorderUow(),
        aggregate_uow=aggregate_uow,
        authorization_port=authorization,
        idempotency_port=unused,
        inquiry_abuse_protection_port=unused,
        portfolio_creation_port=unused,
    )


def test_update_portfolio_caption_command_coerces_ids():
    actor = AuthenticatedActor(user_id=uuid.uuid4())
    vendor_id = uuid.uuid4()
    media_id = uuid.uuid4()

    command = UpdatePortfolioCaptionCommand(
        actor=actor,
        vendor_id=str(vendor_id),
        media_id=str(media_id),
        expected_version=2,
        caption="New caption",
    )

    assert command.actor is actor
    assert command.vendor_id == vendor_id
    assert command.media_id == media_id
    assert command.expected_version == 2
    assert command.caption == "New caption"


def test_update_portfolio_caption_persists_event_and_state():
    vendor_id = uuid.uuid4()
    actor = AuthenticatedActor(user_id=uuid.uuid4())
    media = _media(
        vendor_id,
        caption="Old caption",
        visibility_status=PortfolioVisibilityStatus.APPROVED.value,
        version=3,
    )
    image_repo = ImageRepo(media)
    aggregate_uow = AggregateMutationUow()
    authorization = AllowOwner()
    handler = _handler(image_repo, aggregate_uow, authorization)

    result = handler.update_portfolio_caption(
        UpdatePortfolioCaptionCommand(
            actor=actor,
            vendor_id=vendor_id,
            media_id=media.id,
            expected_version=3,
            caption="New caption",
        )
    )

    assert authorization.calls == [(actor, vendor_id)]
    assert image_repo.get_for_vendor_calls == [(vendor_id, media.id)]
    assert len(aggregate_uow.save_calls) == 1
    saved, expected_version = aggregate_uow.save_calls[0]
    assert saved is media
    assert expected_version == 3
    assert [event.__class__.__name__ for event in aggregate_uow.events] == ["PortfolioCaptionUpdated"]
    assert result.id == media.id
    assert result.caption == "New caption"
    assert result.visibility_status == PortfolioVisibilityStatus.WAITING_APPROVAL.value
    assert result.version == 4


def test_update_portfolio_caption_same_value_is_noop_without_persistence():
    vendor_id = uuid.uuid4()
    media = _media(vendor_id, caption="Same caption", version=3)
    image_repo = ImageRepo(media)
    aggregate_uow = AggregateMutationUow()
    handler = _handler(image_repo, aggregate_uow, AllowOwner())

    result = handler.update_portfolio_caption(
        UpdatePortfolioCaptionCommand(
            actor=AuthenticatedActor(user_id=uuid.uuid4()),
            vendor_id=vendor_id,
            media_id=media.id,
            expected_version=3,
            caption="Same caption",
        )
    )

    assert aggregate_uow.save_calls == []
    assert result.caption == "Same caption"
    assert result.version == 3


def test_update_portfolio_caption_stale_version_prevents_transition_and_persistence():
    vendor_id = uuid.uuid4()
    media = _media(vendor_id, caption="Old caption", version=3)
    image_repo = ImageRepo(media)
    aggregate_uow = AggregateMutationUow()
    handler = _handler(image_repo, aggregate_uow, AllowOwner())

    with pytest.raises(VendorVersionConflict) as exc_info:
        handler.update_portfolio_caption(
            UpdatePortfolioCaptionCommand(
                actor=AuthenticatedActor(user_id=uuid.uuid4()),
                vendor_id=vendor_id,
                media_id=media.id,
                expected_version=1,
                caption="New caption",
            )
        )

    conflict = exc_info.value
    assert conflict.resource_id == media.id
    assert conflict.expected_version == 1
    assert conflict.actual_version == 3
    assert aggregate_uow.save_calls == []
    assert media.caption == "Old caption"
    assert media.version == 3
