from __future__ import annotations

from collections.abc import Callable
import uuid

from django.db import IntegrityError, transaction
from django.db.models import Max

from application.vendors.errors import VendorConflict, VendorResourceNotFound
from domain.vendors.entities import PortfolioImage
from django_app.vendors.models import PortfolioImage as DjangoImage
from django_app.vendors.models import VendorProfile as DjangoVendor

from .django_vendor_aggregate_uow import DjangoVendorAggregateUnitOfWork


class DjangoPortfolioImageCreationPort:
    """Assign the next active vendor order and persist media/events atomically."""

    def __init__(self, aggregate_uow: DjangoVendorAggregateUnitOfWork | None = None) -> None:
        self.aggregate_uow = aggregate_uow or DjangoVendorAggregateUnitOfWork()

    def create_at_next_order(
        self,
        *,
        vendor_id: uuid.UUID,
        image_factory: Callable[[int], PortfolioImage],
    ) -> PortfolioImage:
        try:
            with transaction.atomic():
                try:
                    DjangoVendor.objects.select_for_update().get(id=vendor_id)
                except DjangoVendor.DoesNotExist as exc:
                    raise VendorResourceNotFound(
                        "Vendor not found.",
                        code="vendor_not_found",
                    ) from exc

                max_order = (
                    DjangoImage.all_objects.filter(
                        vendor_id=vendor_id,
                        is_active=True,
                        is_deleted=False,
                    ).aggregate(max_order=Max("order"))["max_order"]
                )
                image = image_factory((max_order if max_order is not None else -1) + 1)
                if image.vendor_id != vendor_id:
                    raise VendorConflict(
                        "Portfolio image vendor does not match the locked vendor.",
                        code="vendor_portfolio_owner_mismatch",
                    )
                return self.aggregate_uow.add_with_pending_events(image)
        except IntegrityError as exc:
            raise VendorConflict(
                "Portfolio order changed during creation. Retry the request.",
                code="vendor_portfolio_order_conflict",
            ) from exc
