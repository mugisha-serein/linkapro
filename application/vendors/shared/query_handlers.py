from __future__ import annotations

from typing import Callable

from domain.vendors.inquiries.interfaces import IInquiryRepository
from domain.vendors.portfolio.interfaces import IPortfolioImageRepository
from domain.vendors.profile.interfaces import IVendorProfileRepository
from domain.vendors.shared.pagination import Page
from application.vendors.analytics.queries import GetVendorAnalyticsQuery, GetVendorDashboardSummaryQuery, ListRecentVendorActivityQuery
from application.vendors.errors import VendorApplicationConfigurationError
from application.vendors.inquiries.queries import ListInquiriesQuery
from application.vendors.packages.queries import ListServicePackagesQuery
from application.vendors.portfolio.queries import ListPortfolioImagesQuery
from application.vendors.profile.queries import GetVendorQuery
from application.vendors.shared.dtos import PageDTO
from application.vendors.shared.mappers import VendorDTOMapperMixin
from application.vendors.shared.ports import VendorAuthorizationPort
from application.vendors.analytics.ports import VendorReadPort


class BaseVendorQueryHandler(VendorDTOMapperMixin):
        def __init__(
            self,
            vendor_repo: IVendorProfileRepository,
            image_repo: IPortfolioImageRepository,
            inquiry_repo: IInquiryRepository,
            read_repo: VendorReadPort,
            authorization_port: VendorAuthorizationPort | None = None,
        ):
            if read_repo is None:
                raise VendorApplicationConfigurationError(field_errors={"read_repo": ["Vendor read port is required."]})
            self.vendor_repo = vendor_repo
            self.image_repo = image_repo
            self.inquiry_repo = inquiry_repo
            self.read_repo = read_repo
            self.authorization_port = authorization_port

        def _assert_actor_can_access_vendor(
            self,
            query: (
                GetVendorQuery
                | ListPortfolioImagesQuery
                | ListServicePackagesQuery
                | ListInquiriesQuery
                | GetVendorDashboardSummaryQuery
                | GetVendorAnalyticsQuery
                | ListRecentVendorActivityQuery
            ),
        ) -> None:
            if self.authorization_port is None:
                raise VendorApplicationConfigurationError(
                    field_errors={"authorization_port": ["Vendor authorization is required."]}
                )
            self.authorization_port.assert_actor_can_access_vendor(query.actor, query.vendor_id)

        @staticmethod
        def _map_page(page: Page, mapper: Callable) -> PageDTO:
            return PageDTO(
                items=tuple(mapper(item) for item in page.items),
                total=page.total,
                limit=page.limit,
                offset=page.offset,
                next_cursor=page.next_cursor,
            )
