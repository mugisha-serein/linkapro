from __future__ import annotations

from typing import Any

from django.db import transaction

from application.vendors.errors import VendorApplicationConfigurationError
from domain.vendors.entities import Inquiry, PortfolioImage, ServicePackage, VendorProfile
from infrastructure.adapters.django_vendor_event_outbox import DjangoVendorEventOutboxDispatcher
from infrastructure.repos.django_inquiry_repository import DjangoInquiryRepository
from infrastructure.repos.django_portfolio_image_repository import DjangoPortfolioImageRepository
from infrastructure.repos.django_service_package_repository import DjangoServicePackageRepository
from infrastructure.repos.django_vendor_profile_repository import DjangoVendorProfileRepository


class DjangoVendorAggregateUnitOfWork:
    """Persist one vendor aggregate and its pending events in one DB transaction."""

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
        with transaction.atomic():
            saved = repository.add(aggregate)
            self._persist_pending_events(aggregate)
            return saved

    def save_with_pending_events(self, aggregate, *, expected_version: int):
        repository = self._repository_for(aggregate)
        with transaction.atomic():
            saved = repository.save(aggregate, expected_version=expected_version)
            self._persist_pending_events(aggregate)
            return saved

    def _persist_pending_events(self, aggregate: Any) -> None:
        pull_events = getattr(aggregate, "pull_events", None)
        if not callable(pull_events):
            raise VendorApplicationConfigurationError(
                field_errors={"aggregate": ["Vendor aggregate must expose pull_events()."]}
            )
        for event in pull_events():
            self.event_outbox.dispatch(event)

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
