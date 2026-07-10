from __future__ import annotations

from typing import Sequence
import uuid

from django.db import transaction
from django.db.models import F, Max

from application.vendors.errors import InvalidVendorCommand, VendorResourceNotFound, VendorVersionConflict
from domain.vendors.entities import PortfolioImage
from django_app.vendors.models import PortfolioImage as DjangoImage

from .django_portfolio_image_repository import DjangoPortfolioImageRepository


class DjangoPortfolioReorderUnitOfWork:
    """Load and atomically persist one vendor's complete active portfolio order."""

    def __init__(self) -> None:
        self._repo = DjangoPortfolioImageRepository()

    def load_active_vendor_images(self, vendor_id: uuid.UUID) -> Sequence[PortfolioImage]:
        rows = (
            DjangoImage.all_objects.filter(
                vendor_id=vendor_id,
                is_active=True,
                is_deleted=False,
            )
            .order_by("order", "id")
        )
        return tuple(self._repo._to_domain(row) for row in rows)

    def persist_reorder(
        self,
        vendor_id: uuid.UUID,
        images: Sequence[PortfolioImage],
        *,
        expected_versions: dict[uuid.UUID, int],
    ) -> Sequence[PortfolioImage]:
        image_ids = [image.id for image in images]
        if len(image_ids) != len(set(image_ids)):
            raise InvalidVendorCommand(
                field_errors={"image_ids_in_order": ["Duplicate portfolio images are not allowed."]}
            )

        with transaction.atomic():
            locked = list(
                DjangoImage.all_objects.select_for_update()
                .filter(vendor_id=vendor_id, is_active=True, is_deleted=False)
                .order_by("order", "id")
            )
            locked_by_id = {image.id: image for image in locked}
            if set(expected_versions) != set(locked_by_id):
                raise VendorResourceNotFound("Portfolio set changed; reload before reordering.")
            if set(image_ids) - set(locked_by_id):
                raise VendorResourceNotFound("Image not found.")

            for image_id, expected_version in expected_versions.items():
                actual_version = locked_by_id[image_id].version
                if actual_version != expected_version:
                    raise VendorVersionConflict(
                        resource_id=image_id,
                        expected_version=expected_version,
                        actual_version=actual_version,
                    )

            max_order = (
                DjangoImage.all_objects.filter(
                    vendor_id=vendor_id,
                    is_active=True,
                    is_deleted=False,
                ).aggregate(max_order=Max("order"))["max_order"]
            )
            temporary_start = (max_order if max_order is not None else -1) + len(locked) + 1

            for index, image in enumerate(images):
                moved = DjangoImage.all_objects.filter(
                    id=image.id,
                    vendor_id=vendor_id,
                    version=expected_versions[image.id],
                    is_active=True,
                    is_deleted=False,
                ).update(order=temporary_start + index)
                if moved != 1:
                    current = DjangoImage.all_objects.filter(id=image.id).values_list("version", flat=True).first()
                    raise VendorVersionConflict(
                        resource_id=image.id,
                        expected_version=expected_versions[image.id],
                        actual_version=current if current is not None else expected_versions[image.id] + 1,
                    )

            for image in images:
                updated = DjangoImage.all_objects.filter(
                    id=image.id,
                    vendor_id=vendor_id,
                    version=expected_versions[image.id],
                    is_active=True,
                    is_deleted=False,
                ).update(
                    order=image.order,
                    version=F("version") + 1,
                    updated_at=image.updated_at,
                )
                if updated != 1:
                    current = DjangoImage.all_objects.filter(id=image.id).values_list("version", flat=True).first()
                    raise VendorVersionConflict(
                        resource_id=image.id,
                        expected_version=expected_versions[image.id],
                        actual_version=current if current is not None else expected_versions[image.id] + 1,
                    )

            persisted = list(
                DjangoImage.all_objects.select_related("vendor").filter(
                    id__in=image_ids,
                    vendor_id=vendor_id,
                )
            )
            if len(persisted) != len(image_ids):
                raise VendorResourceNotFound("Portfolio set changed during reorder.")

        persisted_by_id = {image.id: self._repo._to_domain(image) for image in persisted}
        return tuple(persisted_by_id[image_id] for image_id in image_ids)
