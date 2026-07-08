from __future__ import annotations

from collections import Counter
from typing import Sequence
import uuid

from django.db import transaction
from django.db.models import F, Max

from application.vendors.errors import InvalidVendorCommand, VendorConflict, VendorResourceNotFound
from domain.vendors.entities import PortfolioImage
from domain.vendors.interfaces import Page, PageRequest
from django_app.vendors.models import PortfolioImage as DjangoImage

from .django_portfolio_image_repository import DjangoPortfolioImageRepository


class DjangoPortfolioReorderUnitOfWork:
    def __init__(self) -> None:
        self._repo = DjangoPortfolioImageRepository()

    def list_vendor_images(self, vendor_id: uuid.UUID, page: PageRequest) -> Page[PortfolioImage]:
        return self._repo.list_by_vendor(vendor_id, page)

    def persist_reorder(
        self,
        vendor_id: uuid.UUID,
        images: Sequence[PortfolioImage],
        *,
        expected_versions: dict[uuid.UUID, int],
    ) -> Sequence[PortfolioImage]:
        image_ids = [image.id for image in images]
        if len(image_ids) != len(set(image_ids)):
            raise InvalidVendorCommand(field_errors={"image_ids_in_order": ["Duplicate portfolio images are not allowed."]})

        with transaction.atomic():
            locked = list(
                DjangoImage.all_objects.select_for_update()
                .filter(vendor_id=vendor_id, is_active=True, is_deleted=False)
                .order_by("order", "id")
            )
            locked_by_id = {image.id: image for image in locked}
            if set(expected_versions) != set(locked_by_id):
                raise VendorResourceNotFound("Image not found.")
            missing_changed = [image_id for image_id in image_ids if image_id not in locked_by_id]
            if missing_changed:
                raise VendorResourceNotFound("Image not found.")
            for image_id, expected_version in expected_versions.items():
                if locked_by_id[image_id].version != expected_version:
                    raise VendorConflict(
                        "Portfolio item was updated by another request.",
                        code="vendor_version_conflict",
                        field_errors={"version": ["Portfolio item was updated by another request."]},
                    )

            max_order = (
                DjangoImage.all_objects.filter(vendor_id=vendor_id, is_active=True, is_deleted=False)
                .aggregate(max_order=Max("order"))["max_order"]
            ) or 0
            temporary_start = max_order + len(locked) + 1
            for index, image in enumerate(images):
                DjangoImage.all_objects.filter(id=image.id).update(order=temporary_start + index)
            for image in images:
                DjangoImage.all_objects.filter(id=image.id, version=expected_versions[image.id]).update(
                    order=image.order,
                    version=F("version") + 1,
                    updated_at=image.updated_at,
                )
            persisted = list(DjangoImage.all_objects.select_related("vendor").filter(id__in=image_ids))

        persisted_by_id = {image.id: self._repo._to_domain(image) for image in persisted}
        return tuple(persisted_by_id[image_id] for image_id in image_ids)
