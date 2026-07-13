from __future__ import annotations

import uuid
from typing import Sequence

from domain.vendors.entities import PortfolioImage, VendorProfile, VendorStatus
from domain.vendors.interfaces import PageRequest
from application.vendors.errors import InvalidVendorCommand, VendorOperationForbidden, VendorResourceNotFound
from application.vendors.portfolio.commands import (
    AddPortfolioImageCommand,
    DeletePortfolioImageCommand,
    MarkPortfolioMediaProcessingCommand,
    MarkPortfolioMediaUploadedCommand,
    QueuePortfolioMediaCommand,
    ReorderPortfolioImagesCommand,
    UpdatePortfolioCaptionCommand,
)
from application.vendors.portfolio.dtos import PortfolioImageDTO
from application.vendors.portfolio.queries import ListPortfolioImagesQuery
from application.vendors.shared.dtos import PageDTO


PORTFOLIO_MEDIA_CREATION_FORBIDDEN_STATUSES = frozenset({VendorStatus.SUSPENDED})


def ensure_vendor_can_add_portfolio_media(profile: VendorProfile | None) -> None:
    if profile is None:
        raise VendorResourceNotFound("Vendor not found.", code="vendor_not_found")
    if profile.status in PORTFOLIO_MEDIA_CREATION_FORBIDDEN_STATUSES:
        raise VendorOperationForbidden(
            "Vendor cannot add portfolio media while suspended.",
            code="vendor_portfolio_media_creation_forbidden",
        )



class PortfolioCommandHandlersMixin:
        def add_portfolio_image(self, cmd: AddPortfolioImageCommand) -> PortfolioImageDTO:
            self._assert_actor_owns_vendor(cmd.actor, cmd.vendor_id)

            def operation() -> PortfolioImageDTO:
                profile = self.vendor_repo.get_by_id(cmd.vendor_id)
                ensure_vendor_can_add_portfolio_media(profile)
                def image_factory(next_order: int) -> PortfolioImage:
                    return PortfolioImage(
                        id=cmd.image_id or uuid.uuid4(),
                        vendor_id=cmd.vendor_id,
                        public_id=cmd.public_id,
                        secure_url=cmd.secure_url,
                        caption=cmd.caption,
                        order=next_order,
                        media_type=cmd.media_type,
                        upload_status=cmd.upload_status,
                        quality_status=cmd.quality_status,
                        visibility_status=cmd.visibility_status,
                        original_filename=cmd.original_filename,
                        mime_type=cmd.mime_type,
                        file_size=cmd.file_size,
                        cloudinary_public_id=cmd.cloudinary_public_id,
                        cloudinary_secure_url=cmd.cloudinary_secure_url,
                        width=cmd.width,
                        height=cmd.height,
                    )

                saved = self.portfolio_creation_port.create_at_next_order(
                    vendor_id=cmd.vendor_id,
                    image_factory=image_factory,
                )
                return self._to_image_dto(saved)

            return self._run_required_idempotent("portfolio_image.add", cmd.actor.user_id, cmd.idempotency_key, cmd, operation)

        def queue_portfolio_media(self, cmd: QueuePortfolioMediaCommand) -> PortfolioImageDTO:
            return self._execute_transition(
                authorize=lambda: self._assert_actor_owns_vendor(cmd.actor, cmd.vendor_id),
                loader=lambda: self._get_image_or_raise(cmd.vendor_id, cmd.media_id),
                expected_version=cmd.expected_version,
                transition=lambda media: media.mark_queued(),
                to_dto=self._to_image_dto,
            )

        def mark_portfolio_media_processing(
            self,
            cmd: MarkPortfolioMediaProcessingCommand,
        ) -> PortfolioImageDTO:
            return self._execute_transition(
                authorize=lambda: self._assert_actor_owns_vendor(cmd.actor, cmd.vendor_id),
                loader=lambda: self._get_image_or_raise(cmd.vendor_id, cmd.media_id),
                expected_version=cmd.expected_version,
                transition=lambda media: media.mark_processing(),
                to_dto=self._to_image_dto,
            )

        def mark_portfolio_media_uploaded(
            self,
            cmd: MarkPortfolioMediaUploadedCommand,
        ) -> PortfolioImageDTO:
            return self._execute_transition(
                authorize=lambda: self._assert_actor_owns_vendor(cmd.actor, cmd.vendor_id),
                loader=lambda: self._get_image_or_raise(cmd.vendor_id, cmd.media_id),
                expected_version=cmd.expected_version,
                transition=lambda media: media.mark_uploaded(public_id=cmd.public_id, secure_url=cmd.secure_url),
                to_dto=self._to_image_dto,
            )

        def update_portfolio_caption(
            self,
            cmd: UpdatePortfolioCaptionCommand,
        ) -> PortfolioImageDTO:
            return self._execute_transition(
                authorize=lambda: self._assert_actor_owns_vendor(cmd.actor, cmd.vendor_id),
                loader=lambda: self._get_image_or_raise(cmd.vendor_id, cmd.media_id),
                expected_version=cmd.expected_version,
                transition=lambda media: media.update_caption(cmd.caption),
                to_dto=self._to_image_dto,
            )

        def delete_portfolio_image(self, cmd: DeletePortfolioImageCommand) -> None:
            return self._execute_transition(
                authorize=lambda: self._assert_actor_owns_vendor(cmd.actor, cmd.vendor_id),
                loader=lambda: self._get_image_or_raise(cmd.vendor_id, cmd.image_id),
                expected_version=cmd.expected_version,
                transition=lambda image: image.deactivate(),
                to_dto=lambda image: None,
            )

        def reorder_portfolio_images(self, cmd: ReorderPortfolioImagesCommand) -> PageDTO[PortfolioImageDTO]:
            self._assert_actor_owns_vendor(cmd.actor, cmd.vendor_id)
            images = self._load_active_vendor_images(cmd.vendor_id)
            image_map = {image.id: image for image in images}
            requested_ids = tuple(cmd.image_ids_in_order)
            self._validate_portfolio_reorder_ids(requested_ids, image_map)
            expected_versions = {item.resource_id: item.expected_version for item in cmd.expected_versions}
            if set(expected_versions) != set(requested_ids):
                raise InvalidVendorCommand(field_errors={"expected_versions": ["Expected versions must match image order."]})
            for image_id, expected_version in expected_versions.items():
                self._assert_expected_version(image_id, image_map[image_id].version, expected_version)

            changed: list[PortfolioImage] = []
            for index, image_id in enumerate(requested_ids):
                image = image_map[image_id]
                if image.order == index:
                    continue
                image.reorder(index)
                changed.append(image)

            if changed:
                persisted = tuple(
                    self.reorder_uow.persist_reorder(cmd.vendor_id, changed, expected_versions=expected_versions)
                )
                image_map.update({image.id: image for image in persisted})

            ordered = tuple(self._to_image_dto(image_map[image_id]) for image_id in requested_ids)
            return PageDTO(items=ordered, total=len(images), limit=len(images), offset=0)


class PortfolioQueryHandlersMixin:
        def list_portfolio_images(self, query: ListPortfolioImagesQuery) -> PageDTO[PortfolioImageDTO]:
            self._assert_actor_can_access_vendor(query)
            images = self.image_repo.list_by_vendor(query.vendor_id, query.page or PageRequest())
            return self._map_page(images, self._to_image_dto)
