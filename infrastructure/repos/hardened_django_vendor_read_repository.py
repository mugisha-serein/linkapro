from __future__ import annotations

import uuid

from application.vendors.dtos import VendorAnalyticsDTO

from .django_vendor_read_repository import DjangoVendorReadRepository


class HardenedDjangoVendorReadRepository(DjangoVendorReadRepository):
    """Build analytics DTOs from one normalized metrics mapping."""

    def analytics(self, vendor_id: uuid.UUID) -> VendorAnalyticsDTO:
        metrics = self.vendor_metrics(vendor_id)
        total = metrics["total_inquiries"]
        read = metrics["read_inquiries"]
        analytics_metrics = {
            **metrics,
            "response_rate": round((read / total) * 100, 2) if total else 0.0,
        }
        return VendorAnalyticsDTO(
            **analytics_metrics,
            avg_response_time_hours=None,
            conversion_rate=None,
            unavailable_metrics=("avg_response_time_hours", "conversion_rate"),
        )
