from __future__ import annotations

from collections.abc import Callable
import uuid

from django.db import IntegrityError, transaction
from django.db.models import Max

from application.vendors.errors import VendorConflict, VendorResourceNotFound
from application.vendors.ports import PortfolioImageCreationPort
from domain.vendors.entities import PortfolioImage
from django_app.vendors.models import PortfolioImage as DjangoImage
from django_app.vendors.models import VendorProfile as DjangoVendor

from .django_vendor_aggregate_uow import DjangoVendorAggregateUnitOfWork


_ACTIVE_ORDER_CONSTRAINT = "vendors_portfolio_active_order_unique"
_MAX_ORDER_RACE_ATTEMPTS = 3


class DjangoPortfolioImageCreationPort(PortfolioImageCreationPort):
    """Assign one active vendor order and persist media/events atomically."""

    def __init__(self, aggregate_uow: DjangoVendorAggregateUnitOfWork | None = None) -> None:
        self.aggregate_uow = aggregate_uow or DjangoVendorAggregateUnitOfWork()

    def create_at_next_order(
        self,
        *,
        vendor_id: uuid.UUID,
        image_factory: Callable[[int], PortfolioImage],
    ) -> PortfolioImage:
        image: PortfolioImage | None = None

        for attempt in range(_MAX_ORDER_RACE_ATTEMPTS):
            try:
                with transaction.atomic():
                    try:
                        DjangoVendor.objects.select_for_update().get(id=vendor_id)
                    except DjangoVendor.DoesNotExist as exc:
                        raise VendorResourceNotFound(
                            "Vendor not found.",
                            code="vendor_not_found",
                        ) from exc

                    next_order = self._next_active_order(vendor_id)
                    if image is None:
                        image = image_factory(next_order)
                        if image.vendor_id != vendor_id:
                            raise VendorConflict(
                                "Portfolio image vendor does not match the locked vendor.",
                                code="vendor_portfolio_owner_mismatch",
                            )
                    else:
                        # order is creation metadata rather than protected lifecycle state.
                        image.order = next_order
                        image.validate_invariants()

                    return self.aggregate_uow.add_with_pending_events(image)
            except IntegrityError as exc:
                if not self._is_active_order_conflict(exc):
                    raise
                if attempt + 1 >= _MAX_ORDER_RACE_ATTEMPTS:
                    raise VendorConflict(
                        "Portfolio order changed during creation. Retry the request.",
                        code="vendor_portfolio_order_conflict",
                    ) from exc

        raise AssertionError("portfolio creation retry loop exited unexpectedly")

    @staticmethod
    def _next_active_order(vendor_id: uuid.UUID) -> int:
        max_order = (
            DjangoImage.all_objects.filter(
                vendor_id=vendor_id,
                is_active=True,
                is_deleted=False,
            ).aggregate(max_order=Max("order"))["max_order"]
        )
        return (max_order if max_order is not None else -1) + 1

    @staticmethod
    def _is_active_order_conflict(exc: IntegrityError) -> bool:
        cause = exc.__cause__
        diagnostic = getattr(cause, "diag", None)
        constraint_name = getattr(diagnostic, "constraint_name", None)
        if constraint_name is not None:
            return constraint_name == _ACTIVE_ORDER_CONSTRAINT

        message = str(exc).lower()
        return (
            _ACTIVE_ORDER_CONSTRAINT in message
            or (
                "unique" in message
                and "portfolio" in message
                and "vendor" in message
                and "order" in message
            )
        )
