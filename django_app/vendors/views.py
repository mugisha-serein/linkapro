from __future__ import annotations

from pathlib import Path
from importlib import import_module

__path__ = [str(Path(__file__).with_suffix(""))]

_EXPORTS = {
    "AdminPendingVendorListView": ".views.admin",
    "InquiryListView": ".views.inquiries",
    "PublicInquiryView": ".views.inquiries",
    "ServicePackageActivateView": ".views.packages",
    "ServicePackageDetailView": ".views.packages",
    "ServicePackageListView": ".views.packages",
    "PortfolioImageReorderView": ".views.portfolio",
    "PortfolioImageView": ".views.portfolio",
    "PublicVendorProfileView": ".views.profile",
    "VendorActivityView": ".views.analytics",
    "VendorAnalyticsView": ".views.analytics",
    "VendorBrandingMediaView": ".views.profile",
    "VendorCoverImageView": ".views.profile",
    "VendorDashboardSummaryView": ".views.analytics",
    "VendorProfileStatusView": ".views.profile",
    "VendorProfileView": ".views.profile",
    "VendorSubmitForReviewView": ".views.profile",
    "VendorVerificationDocumentView": ".views.profile",
}


def __getattr__(name: str):
    module_path = _EXPORTS.get(name)
    if module_path is None:
        common = import_module(".vendor_view_common", __package__)
        try:
            value = getattr(common, name)
        except AttributeError as exc:
            raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc
    else:
        module = import_module(module_path, __package__)
        value = getattr(module, name)
    globals()[name] = value
    return value


__all__ = sorted(_EXPORTS)
