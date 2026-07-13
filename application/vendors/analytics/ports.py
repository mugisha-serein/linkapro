from __future__ import annotations

from typing import Protocol
import uuid

from domain.vendors.interfaces import PageRequest
from application.vendors.analytics.dtos import VendorActivityDTO, VendorAnalyticsDTO, VendorDashboardSummaryDTO
from application.vendors.packages.dtos import ServicePackageDTO
from application.vendors.shared.dtos import PageDTO

class VendorReadPort(Protocol):
    def list_service_packages(self, vendor_id: uuid.UUID, page: PageRequest) -> PageDTO[ServicePackageDTO]: ...

    def dashboard_summary(self, vendor_id: uuid.UUID) -> VendorDashboardSummaryDTO: ...

    def analytics(self, vendor_id: uuid.UUID) -> VendorAnalyticsDTO: ...

    def recent_activity(self, vendor_id: uuid.UUID, page: PageRequest) -> PageDTO[VendorActivityDTO]: ...
