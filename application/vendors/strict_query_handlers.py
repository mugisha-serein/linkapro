from __future__ import annotations

from typing import TypeVar

from .errors import InvalidVendorCommand
from .handlers import VendorQueryHandlers
from .queries import (
    GetVendorAnalyticsQuery,
    GetVendorDashboardSummaryQuery,
    GetVendorQuery,
    ListInquiriesQuery,
    ListPortfolioImagesQuery,
    ListRecentVendorActivityQuery,
    ListServicePackagesQuery,
)

QueryT = TypeVar("QueryT")


class StrictVendorQueryHandlers(VendorQueryHandlers):
    """Reject invalid query objects before authorization or repository access."""

    @staticmethod
    def _require_query(query: object, expected_type: type[QueryT]) -> QueryT:
        if not isinstance(query, expected_type):
            raise InvalidVendorCommand(
                "Vendor query is invalid.",
                code="vendor_query_invalid",
                field_errors={
                    "query": [f"Expected {expected_type.__name__}."],
                },
            )
        return query

    def get_vendor(self, query: GetVendorQuery):
        return super().get_vendor(self._require_query(query, GetVendorQuery))

    def list_portfolio_images(self, query: ListPortfolioImagesQuery):
        return super().list_portfolio_images(
            self._require_query(query, ListPortfolioImagesQuery)
        )

    def list_service_packages(self, query: ListServicePackagesQuery):
        return super().list_service_packages(
            self._require_query(query, ListServicePackagesQuery)
        )

    def list_inquiries(self, query: ListInquiriesQuery):
        return super().list_inquiries(self._require_query(query, ListInquiriesQuery))

    def get_dashboard_summary(self, query: GetVendorDashboardSummaryQuery):
        return super().get_dashboard_summary(
            self._require_query(query, GetVendorDashboardSummaryQuery)
        )

    def get_analytics(self, query: GetVendorAnalyticsQuery):
        return super().get_analytics(self._require_query(query, GetVendorAnalyticsQuery))

    def get_recent_activity(self, query: ListRecentVendorActivityQuery):
        return super().get_recent_activity(
            self._require_query(query, ListRecentVendorActivityQuery)
        )
