from __future__ import annotations

import uuid

import pytest

from application.vendors.commands import AuthenticatedActor
from application.vendors.errors import VendorVersionConflict
from application.vendors.handlers import VendorCommandHandlers
from application.vendors.portfolio_media_commands import MarkPortfolioMediaProcessingCommand
import application.vendors.portfolio_media_processing_handler  # noqa: F401 - registers handler method
from domain.vendors.entities import PortfolioImage, PortfolioQualityStatus, PortfolioUploadStatus, PortfolioVisibilityStatus
from domain.vendors.errors import InvalidPortfolioTransition


class StrictUnusedDependency:
    def __getattr__(self, name):
        raise AssertionError(f"Unexpected dependency access: {name}")


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


def _media(vendor_id: uuid.UUID, *, upload_status: str, version: int = 3) -> PortfolioImage:
    return PortfolioImage(
        id=uuid.uuid4(),
        vendor_id=vendor_id,
        public_id="asset",
        secure_url="https://example.com/media.jpg",
        upload_status=upload_status,
        quality_status=PortfolioQualityStatus.PENDING_ANALYSIS.value,
        visibility_status=PortfolioVisibilityStatus.PRIVATE.value,
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
        portfolio_creation_port=unused,
    )


def test_mark_portfolio_media_processing_command_coerces_ids():
    actor = AuthenticatedActor(user_id=uuid.uuid4())
    vendor_id = uuid.uuid4()
    media_id = uuid.uuid4()

    command = MarkPortfolioMediaProcessingCommand(
        actor=actor,
        vendor_id=str(vendor_id),
        media_id=str(media_id),
        expected_version=2,
    )

    assert command.actor is actor
    assert command.vendor_id == vendor_id
    assert command.media_id == media_id
    assert command.expected_version == 2


def test_mark_portfolio_media_processing_from_queued_state_persists_transition():
    vendor_id = uuid.uuid4()
    actor = AuthenticatedActor(user_id=uuid.uuid4())
    media = _media(vendor_id, upload_status=PortfolioUploadStatus.QUEUED.value, version=3)
    image_repo = ImageRepo(media)
    aggregate_uow = AggregateMutationUow()
    authorization = AllowOwner()
    handler = _handler(image_repo, aggregate_uow, authorization)

    result = handler.mark_portfolio_media_processing(
        MarkPortfolioMediaProcessingCommand(
            actor=actor,
            vendor_id=vendor_id,
            media_id=media.id,
            expected_version=3,
        )
    )

    assert authorization.calls == [(actor, vendor_id)]
    assert image_repo.get_for_vendor_calls == [(vendor_id, media.id)]
    assert len(aggregate_uow.save_calls) == 1
    saved, expected_version = aggregate_uow.save_calls[0]
    assert saved is media
    assert expected_version == 3
    assert [event.__class__.__name__ for event in aggregate_uow.events] == [
        "PortfolioMediaProcessingStarted"
    ]
    assert result.id == media.id
    assert result.upload_status == PortfolioUploadStatus.PROCESSING.value
    assert result.visibility_status == PortfolioVisibilityStatus.PRIVATE.value
    assert result.version == 4


def test_mark_portfolio_media_processing_from_invalid_lifecycle_state_does_not_persist():
    vendor_id = uuid.uuid4()
    media = _media(vendor_id, upload_status=PortfolioUploadStatus.STAGED.value, version=3)
    image_repo = ImageRepo(media)
    aggregate_uow = AggregateMutationUow()
    handler = _handler(image_repo, aggregate_uow, AllowOwner())

    with pytest.raises(InvalidPortfolioTransition) as exc_info:
        handler.mark_portfolio_media_processing(
            MarkPortfolioMediaProcessingCommand(
                actor=AuthenticatedActor(user_id=uuid.uuid4()),
                vendor_id=vendor_id,
                media_id=media.id,
                expected_version=3,
            )
        )

    assert str(exc_info.value) == "Only queued media can start processing."
    assert aggregate_uow.save_calls == []
    assert media.upload_status == PortfolioUploadStatus.STAGED.value
    assert media.version == 3


def test_mark_portfolio_media_processing_stale_version_prevents_transition_and_persistence():
    vendor_id = uuid.uuid4()
    media = _media(vendor_id, upload_status=PortfolioUploadStatus.QUEUED.value, version=3)
    image_repo = ImageRepo(media)
    aggregate_uow = AggregateMutationUow()
    handler = _handler(image_repo, aggregate_uow, AllowOwner())

    with pytest.raises(VendorVersionConflict) as exc_info:
        handler.mark_portfolio_media_processing(
            MarkPortfolioMediaProcessingCommand(
                actor=AuthenticatedActor(user_id=uuid.uuid4()),
                vendor_id=vendor_id,
                media_id=media.id,
                expected_version=1,
            )
        )

    conflict = exc_info.value
    assert conflict.resource_id == media.id
    assert conflict.expected_version == 1
    assert conflict.actual_version == 3
    assert aggregate_uow.save_calls == []
    assert media.upload_status == PortfolioUploadStatus.QUEUED.value
    assert media.version == 3
