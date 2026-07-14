from __future__ import annotations

from domain.vendors.shared.pagination import PageRequest
from application.vendors.analytics.dtos import (
    VendorActivityDTO,
    VendorAnalyticsDTO,
    VendorDashboardSummaryDTO,
    VendorVisibilityTrendDTO,
    VendorViewsTrendPointDTO,
)
from application.vendors.analytics.queries import (
    GetVendorAnalyticsQuery,
    GetVendorDashboardSummaryQuery,
    GetVendorVisibilityTrendQuery,
    GetVendorViewsTrendQuery,
    ListRecentVendorActivityQuery,
)
from application.vendors.errors import VendorResourceNotFound
from application.vendors.shared.dtos import PageDTO


class AnalyticsQueryHandlersMixin:
        def get_dashboard_summary(self, query: GetVendorDashboardSummaryQuery) -> VendorDashboardSummaryDTO:
            self._assert_actor_can_access_vendor(query)
            if self.vendor_repo.get_by_id(query.vendor_id) is None:
                raise VendorResourceNotFound("Vendor not found.")
            return self.read_repo.dashboard_summary(query.vendor_id)

        def get_analytics(self, query: GetVendorAnalyticsQuery) -> VendorAnalyticsDTO:
            self._assert_actor_can_access_vendor(query)
            return self.read_repo.analytics(query.vendor_id)

        def get_recent_activity(self, query: ListRecentVendorActivityQuery) -> PageDTO[VendorActivityDTO]:
            self._assert_actor_can_access_vendor(query)
            return self.read_repo.recent_activity(query.vendor_id, query.page or PageRequest(limit=10, offset=0))

        def get_views_trend(self, query: GetVendorViewsTrendQuery) -> tuple[VendorViewsTrendPointDTO, ...]:
            self._assert_actor_can_access_vendor(query)
            return self.read_repo.total_views_trend(query.vendor_id, query.months)

        def get_visibility_trend(self, query: GetVendorVisibilityTrendQuery) -> VendorVisibilityTrendDTO:
            self._assert_actor_can_access_vendor(query)
            return self.read_repo.visibility_trend(query.vendor_id, query.months)
