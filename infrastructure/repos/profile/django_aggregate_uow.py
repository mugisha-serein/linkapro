from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from django.db import transaction

from application.vendors.errors import VendorApplicationConfigurationError
from application.vendors.ports import VendorAggregateUnitOfWork
from domain.vendors.entities import Inquiry, PortfolioImage, ServicePackage, VendorProfile
from infrastructure.adapters.django_vendor_event_outbox import DjangoVendorEventOutboxDispatcher
from infrastructure.repos.inquiries.django_repository import DjangoInquiryRepository
from infrastructure.repos.packages.django_repository import DjangoServicePackageRepository
from infrastructure.repos.portfolio.django_repository import DjangoPortfolioImageRepository
from infrastructure.repos.profile.django_repository import DjangoVendorProfileRepository


class DjangoVendorAggregateUnitOfWork(VendorAggregateUnitOfWork):
    """Persist one vendor aggregate and its pending events in one transaction."""

    def __init__(
        self,
        *,
        vendor_repo: DjangoVendorProfileRepository | None = None,
        image_repo: DjangoPortfolioImageRepository | None = None,
        package_repo: DjangoServicePackageRepository | None = None,
        inquiry_repo: DjangoInquiryRepository | None = None,
        event_outbox: DjangoVendorEventOutboxDispatcher | None = None,
    ) -> None:
        self.vendor_repo = vendor_repo or DjangoVendorProfileRepository()
        self.image_repo = image_repo or DjangoPortfolioImageRepository()
        self.package_repo = package_repo or DjangoServicePackageRepository()
        self.inquiry_repo = inquiry_repo or DjangoInquiryRepository()
        self.event_outbox = event_outbox or DjangoVendorEventOutboxDispatcher()

    def add_with_pending_events(self, aggregate):
        repository = self._repository_for(aggregate)
        pending_events = self._snapshot_pending_events(aggregate)

        with transaction.atomic():
            saved = repository.add(aggregate)
            self._persist_events(pending_events)

        self._acknowledge_persisted_events(aggregate, pending_events)
        return saved

    def save_with_pending_events(self, aggregate, *, expected_version: int):
        repository = self._repository_for(aggregate)
        pending_events = self._snapshot_pending_events(aggregate)

        with transaction.atomic():
            saved = repository.save(aggregate, expected_version=expected_version)
            self._persist_events(pending_events)

        self._acknowledge_persisted_events(aggregate, pending_events)
        return saved

    @staticmethod
    def _snapshot_pending_events(aggregate: Any) -> tuple[object, ...]:
        events = getattr(aggregate, "_events", None)
        if not isinstance(events, list):
            raise VendorApplicationConfigurationError(
                field_errors={"aggregate": ["Vendor aggregate must expose an in-memory pending event list."]}
            )
        for event in events:
            if getattr(event, "event_id", None) is None:
                raise VendorApplicationConfigurationError(
                    field_errors={"aggregate": ["Every pending event must expose event_id."]}
                )
        return tuple(events)

    def _persist_events(self, events: Sequence[object]) -> None:
        for event in events:
            self.event_outbox.dispatch(event)

    @staticmethod
    def _acknowledge_persisted_events(aggregate: Any, persisted_events: Sequence[object]) -> None:
        if not persisted_events:
            return
        persisted_ids = {event.event_id for event in persisted_events}
        current_events = getattr(aggregate, "_events", None)
        if not isinstance(current_events, list):
            raise VendorApplicationConfigurationError(
                field_errors={"aggregate": ["Vendor aggregate pending event storage changed unexpectedly."]}
            )
        current_events[:] = [event for event in current_events if event.event_id not in persisted_ids]

    def _repository_for(self, aggregate):
        if isinstance(aggregate, VendorProfile):
            return self.vendor_repo
        if isinstance(aggregate, PortfolioImage):
            return self.image_repo
        if isinstance(aggregate, ServicePackage):
            return self.package_repo
        if isinstance(aggregate, Inquiry):
            return self.inquiry_repo
        raise VendorApplicationConfigurationError(
            field_errors={
                "aggregate": [
                    f"Unsupported vendor aggregate type: {type(aggregate).__name__}."
                ]
            }
        )
